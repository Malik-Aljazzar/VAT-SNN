import torch
import torch.nn.functional as F


def exponential_kernel(tau_steps, length_factor=5):
    """
    Causal exponential kernel exp(-k / tau) for k = 0 … length_factor · tau, normalised to sum 1. Because of the normalisation
    a filtered curve stays in volts.

    Args:
        tau_steps: Time constant of the kernel in time steps.
        length_factor: Length of the kernel in multiples of tau. After 5 · tau the exponential has fallen below 1 %.

    Returns:
        Tensor of shape (length_factor · tau + 1,).
    """
    # time steps k = 0, 1, 2, … covered by the kernel
    k = torch.arange(int(length_factor * tau_steps) + 1, dtype=torch.float32)
    # exponential decay with time constant tau
    kernel = torch.exp(-k / tau_steps)
    # normalise to sum 1
    return kernel / kernel.sum()


def smooth(curves, kernel):
    """
    Filters every curve causally with the kernel: the value at step t is a weighted mean of the steps t, t-1, t-2, …

    Args:
        curves: Voltage curves, shape (b, t).
        kernel: Kernel from exponential_kernel, already on the device of the curves.

    Returns:
        Filtered curves, shape (b, t).
    """
    # conv1d computes a cross-correlation, so the kernel is flipped to look into the past
    weight = kernel.flip(0)[None, None, :]
    # number of steps the kernel reaches back
    pad = weight.shape[-1] - 1
    # repeat the first value on the left, so the start of the curve has a full past and the length stays t
    padded = F.pad(curves[:, None, :], (pad, 0), mode="replicate")
    # filter and drop the channel axis again
    return F.conv1d(padded, weight)[:, 0, :]


def van_rossum_loss(prediction, target, tau_steps=3, mse_weight=0.1):
    """
    van Rossum distance between predicted and SPICE curves plus a small share of plain MSE. Both curves are smoothed with a
    causal exponential kernel before they are compared. A spike that is only slightly shifted then still overlaps with the
    true one and costs little, a missing or extra spike costs a full smoothed spike. The plain MSE keeps the spikes sharp and high.

    Args:
        prediction: Predicted output voltage in V, shape (b, t).
        target: SPICE output voltage in V, shape (b, t).
        tau_steps: Time constant of the kernel in time steps. 3 → 30 µs at 10 µs per step.
        mse_weight: Weight of the plain MSE. 0 → pure van Rossum distance.

    Returns:
        Scalar loss in V².
    """
    # kernel on the same device as the curves
    kernel = exponential_kernel(tau_steps).to(prediction.device)
    # mean squared difference of the smoothed curves (van Rossum distance)
    van_rossum = F.mse_loss(smooth(prediction, kernel), smooth(target, kernel))
    # plus the weighted plain MSE of the unsmoothed curves
    return van_rossum + mse_weight * F.mse_loss(prediction, target)
