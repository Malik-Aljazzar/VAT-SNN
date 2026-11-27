import torch
import torch.nn as nn
from constants import N_MISMATCH, N_PROCESS, N_V_T_VALUES, VDD_MIN, VDD_MAX, T_MIN, T_MAX


def build_condition(process, mismatch, vdd, temperature):
    """
    Puts the condition of every sample into one vector: 9 process and 21 mismatch parameters (already N(0,1)) plus VDD and
    temperature, which are scaled linearly to [-1, 1] over the operating range.

    Returns:
        Tensor of shape (b, 32).
    """
    # scale VDD and T linearly to [-1, 1] over the operating range (lower limit → -1, upper limit → +1)
    vdd = 2 * (vdd - VDD_MIN) / (VDD_MAX - VDD_MIN) - 1
    temperature = 2 * (temperature - T_MIN) / (T_MAX - T_MIN) - 1
    return torch.cat([process, mismatch, vdd[:, None], temperature[:, None]], dim=1)


class SurrogateLSTM(nn.Module):
    def __init__(self, hidden_size=128, n_layers=2, dropout=0.0):
        super().__init__()
        # input per time step: the input voltage plus the 32 condition values, which are the same at every step
        self.lstm = nn.LSTM(1 + N_PROCESS + N_MISMATCH + N_V_T_VALUES, hidden_size, n_layers, batch_first=True, dropout=dropout)
        # one output voltage per time step
        self.output_projection = nn.Linear(hidden_size, 1)

    def forward(self, input_voltage, process, mismatch, vdd, temperature):
        condition = build_condition(process, mismatch, vdd, temperature)              # (b, 32)
        # repeat the condition for every time step
        condition = condition[:, None, :].expand(-1, input_voltage.shape[1], -1)     # (b, 500, 32)
        x = torch.cat([input_voltage[:, :, None], condition], dim=2)                 # (b, 500, 33)
        # the LSTM walks through the time steps in order, its state carries the history (e.g. how far the membrane is charged)
        x, _ = self.lstm(x)                                                           # (b, 500, hidden)
        return self.output_projection(x).squeeze(-1)                                 # (b, 500)
