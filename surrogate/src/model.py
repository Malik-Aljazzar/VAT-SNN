import torch
import torch.nn as nn
from constants import N_MISMATCH, N_PROCESS, N_V_T_VALUES, VDD_MIN, VDD_MAX, T_MIN, T_MAX

class SurrogateEmbeddings(nn.Module):
    def __init__(self, d_model: int, n_steps: int = 500):
        super().__init__()
        # Reminder: we have 9 process, 21 mismatch and 2 V/T parameters. We will need an extra layer to tranform all them together
        # into one prefix token. Other approaches are also possible.
        self.parameter_projection = nn.Linear(N_MISMATCH + N_PROCESS + N_V_T_VALUES, d_model)
        # As we don't have a vocabulary in te classic sense of a tranformer, we also use a linear layer to tranform the input voltage
        # into "embeddings"
        self.input_voltage_projection = nn.Linear(1, d_model)
        # learned position vector for prefix + every time step
        self.position = nn.Parameter(torch.zeros(1, n_steps + 1, d_model))

    def forward(self, input_voltage, process, mismatch, vdd, temperature):
        # scale VDD and T linearly to [-1, 1] over the operating range (lower limit → -1, upper limit → +1)
        vdd = 2 * (vdd - VDD_MIN) / (VDD_MAX - VDD_MIN) - 1
        temperature = 2 * (temperature - T_MIN) / (T_MAX - T_MIN) - 1

        condition = torch.cat([process, mismatch, vdd[:, None], temperature[:, None]], dim=1)
        prefix = self.parameter_projection(condition)[:, None, :]          # (b, 1, d)
        steps = self.input_voltage_projection(input_voltage[:, :, None])         # (b, 500, d)
        return torch.cat([prefix, steps], dim=1) + self.position           # (b, 501, d)


class SurrogateTransformer(nn.Module):
    def __init__(self, d_model=64, n_heads=4, n_layers=3, d_feedforward=256, dropout=0.1, n_steps=500):
        super().__init__()
        self.embeddings = SurrogateEmbeddings(d_model, n_steps)
        # one block = self-attention + MLP, each with LayerNorm before (norm_first) and a residual connection around it
        block = nn.TransformerEncoderLayer(d_model, n_heads, d_feedforward, dropout,
                                           activation="gelu", batch_first=True, norm_first=True)
        # n_layers copies of the block, each with its own weights
        self.blocks = nn.TransformerEncoder(block, n_layers, enable_nested_tensor=False)
        # causal mask for prefix + time steps: token i may only look at tokens 0..i
        self.register_buffer("causal_mask", nn.Transformer.generate_square_subsequent_mask(n_steps + 1))

    def forward(self, input_voltage, process, mismatch, vdd, temperature):
        x = self.embeddings(input_voltage, process, mismatch, vdd, temperature)   # (b, 501, d)
        x = self.blocks(x, mask=self.causal_mask, is_causal=True)                 # (b, 501, d)
        # output layer follows next
        return x
