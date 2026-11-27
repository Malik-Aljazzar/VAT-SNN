from dataclasses import dataclass

import numpy as np


def find_spikes(curve, threshold):
    """
    Finds the spikes of one curve. A spike starts where the curve rises above the threshold and lasts until it falls below
    it again.

    Args:
        curve: Voltage curve in V, shape (t,).
        threshold: Spike threshold in V, usually VDD/2.

    Returns:
        Start steps of the spikes, shape (n,), and their peak voltages in V, shape (n,).
    """
    # True wherever the curve lies above the threshold
    above = curve > threshold
    # a spike starts where the curve is above now but was below one step before (+1 because of the one-step shift)
    starts = np.flatnonzero(above[1:] & ~above[:-1]) + 1
    # first step below the threshold again after a spike (+1 because of the one-step shift)
    ends = np.flatnonzero(above[:-1] & ~above[1:]) + 1
    # append the end of the curve as end of a spike that is still running when the curve stops
    ends = np.append(ends, len(curve))
    # end of every spike: the first end after its start
    stops = ends[np.searchsorted(ends, starts)]
    # highest voltage between start and end of every spike
    peaks = np.array([curve[start:stop].max() for start, stop in zip(starts, stops)], dtype=float)
    # start steps and peak voltages
    return starts, peaks


def match_spikes(true_starts, predicted_starts, tolerance):
    """
    Pairs SPICE spikes with surrogate spikes. Two spikes form a pair if their starts are at most tolerance steps apart,
    and every spike has at most one partner. Both lists are sorted in time, so one walk through both lists finds the
    largest possible number of pairs.

    Args:
        true_starts: Start steps of the SPICE spikes, sorted, shape (n,).
        predicted_starts: Start steps of the surrogate spikes, sorted, shape (m,).
        tolerance: Largest allowed distance between two paired starts in time steps.

    Returns:
        Indices of the paired spikes in true_starts and in predicted_starts, both shape (pairs,).
    """
    # indices of the paired spikes in both lists
    true_indices, predicted_indices = [], []
    # current position in both lists
    i, j = 0, 0
    # walk through both lists until one of them is used up
    while i < len(true_starts) and j < len(predicted_starts):
        # distance between the two current spikes in steps, positive if the surrogate spike comes later
        difference = predicted_starts[j] - true_starts[i]
        # close enough: the two spikes form a pair
        if abs(difference) <= tolerance:
            # remember the pair
            true_indices.append(i)
            predicted_indices.append(j)
            # both spikes are used up
            i += 1
            j += 1
        # surrogate spike too early for this and every later SPICE spike: it stays without partner
        elif difference < 0:
            # next surrogate spike
            j += 1
        # SPICE spike too early for this and every later surrogate spike: it stays without partner
        else:
            # next SPICE spike
            i += 1
    # indices as integer arrays
    return np.array(true_indices, dtype=int), np.array(predicted_indices, dtype=int)


@dataclass
class SpikeComparison:
    """Spikes of the surrogate curves compared with the spikes of the SPICE curves."""

    # number of spikes in all SPICE curves
    n_true: int
    # number of spikes in all surrogate curves
    n_predicted: int
    # number of pairs: surrogate spikes with a SPICE spike at most tolerance steps away
    n_hits: int
    # per pair: start of the surrogate spike minus start of the SPICE spike in time steps (positive: surrogate too late)
    timing_error: np.ndarray
    # per pair: peak of the surrogate spike minus peak of the SPICE spike in V (negative: surrogate too low)
    peak_error: np.ndarray

    @property
    def n_missed(self):
        """SPICE spikes without a surrogate partner."""
        # every SPICE spike that is not part of a pair
        return self.n_true - self.n_hits

    @property
    def n_extra(self):
        """Surrogate spikes without a SPICE partner."""
        # every surrogate spike that is not part of a pair
        return self.n_predicted - self.n_hits

    @property
    def f1(self):
        """F1 score 2 · pairs / (SPICE spikes + surrogate spikes): 1 if every spike has a partner, 0 if none has."""
        # all spikes of both sides
        n_spikes = self.n_true + self.n_predicted
        # without any spike on both sides nothing is wrong
        return 2 * self.n_hits / n_spikes if n_spikes > 0 else 1.0


def compare_spikes(prediction, target, vdd, tolerance=3):
    """
    Compares the spikes of surrogate and SPICE curves. A spike starts where vout rises above VDD/2. Every SPICE spike is
    paired with at most one surrogate spike whose start is at most tolerance steps away (match_spikes).

    Args:
        prediction: Surrogate output voltage in V, numpy array of shape (b, t).
        target: SPICE output voltage in V, numpy array of shape (b, t).
        vdd: Supply voltage of every curve in V, numpy array of shape (b,).
        tolerance: Largest allowed distance between two paired starts in time steps. 3 → 30 µs at 10 µs per step.

    Returns:
        SpikeComparison over all curves.
    """
    # counters over all curves
    n_true, n_predicted, n_hits = 0, 0, 0
    # timing and peak errors of all pairs, one array per curve
    timing_errors, peak_errors = [], []
    # one curve at a time
    for k in range(len(target)):
        # spikes of the SPICE curve and of the surrogate curve, threshold VDD/2
        true_starts, true_peaks = find_spikes(target[k], vdd[k] / 2)
        predicted_starts, predicted_peaks = find_spikes(prediction[k], vdd[k] / 2)
        # pairs of spikes that start at most tolerance steps apart
        true_indices, predicted_indices = match_spikes(true_starts, predicted_starts, tolerance)
        # add the spikes and pairs of this curve
        n_true += len(true_starts)
        n_predicted += len(predicted_starts)
        n_hits += len(true_indices)
        # timing error and peak error of every pair of this curve
        timing_errors.append(predicted_starts[predicted_indices] - true_starts[true_indices])
        peak_errors.append(predicted_peaks[predicted_indices] - true_peaks[true_indices])
    # join the errors of all curves (the empty arrays keep concatenate working without any curve)
    timing_error = np.concatenate(timing_errors + [np.array([], dtype=int)])
    peak_error = np.concatenate(peak_errors + [np.array([], dtype=float)])
    # all results in one object
    return SpikeComparison(n_true, n_predicted, n_hits, timing_error, peak_error)
