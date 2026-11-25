from dataclasses import dataclass
import numpy as np
import torch

# number of process and mismatch parameters per chip (Spectre variations=all)
N_PROCESS = 9
N_MISMATCH = 21
N_V_T_VALUES = 2

@dataclass
class SurrogateDataset:
    input_voltage: torch.Tensor
    output_voltage: torch.Tensor
    process_parameters: torch.Tensor
    mismatch_parameters: torch.Tensor
    vdd: torch.Tensor
    temperature: torch.Tensor

    def __post_init__(self):
        """
        This method asserts that the shape of the dataset is correct. n is the number of samples and t the number of voltage measurements
        in the curves.

        Raises:
            AssertionError: If a field does not have the expected shape.
        """
        n, t = self.input_voltage.shape
        assert self.output_voltage.shape == (n, t)
        assert self.process_parameters.shape == (n, N_PROCESS)
        assert self.mismatch_parameters.shape == (n, N_MISMATCH)
        assert self.vdd.shape == (n,)
        assert self.temperature.shape == (n,)

@dataclass
class SurrogateSplits:
    train_split: SurrogateDataset
    validation_split: SurrogateDataset
    test_split: SurrogateDataset


class DatasetBuilder:
    def __init__(self, name, step=10, n_steps=500, seed=0):
        """
        Stores the settings for building the dataset.

        Args:
            name: Name of the dataset, e.g. "ds_all". The raw data is read from ../datasets/<name>/<name>_raw.npz
                (relative to the working directory).
            step: Take every step-th point of the 1 µs grid. Default 10 → one point every 10 µs.
            n_steps: Number of time steps per curve after downsampling. Default 500 → 5 ms.
            seed: Seed for shuffling the groups before the split. Same seed → same split.
        """
        self.name = name
        self.step = step
        self.n_steps = n_steps
        self.seed = seed

    def build(self) -> SurrogateSplits:
        """
        Based on raw data, this method creates a valid dataset for surrogate model training. It splits the dataset into three parts
        for training, validation and testing based on the voltage and temperature groups. The split is made according to the conventional
        70/20/10 rule.

        Returns:
            SurrogateSplits which includes a SurrogateDataset for all the three distinct splits.
        """

        # First, we should get the raw arrays directly from the raw dataset.
        vg1, vout, omega, group, process_parameters, mismatch_parameters = self._get_raw_arrays()

        # Now, we want to generate our splits. We split the samples by v/t-group in order to get different v/t values when testing and validating.
        train_ids, validation_ids, test_ids = self._split_group_ids(group)

        # Now, we can eleganly create the three datasets with the np.isin function. We use torch.from_numpy to convert the numpy arrays to torch tensors
        train_split, validation_split, test_split = self._create_splits(vg1, vout, omega, group, process_parameters, mismatch_parameters, train_ids, validation_ids, test_ids)

        return SurrogateSplits(train_split=train_split, validation_split=validation_split, test_split=test_split)

    def _create_splits(self, vg1, vout, omega, group, process_parameters, mismatch_parameters, train_ids, validation_ids, test_ids):
        """
        Based on raw data arrays and the information 
        """
        train_rows = np.isin(group, train_ids)
        validation_rows = np.isin(group, validation_ids)
        test_rows = np.isin(group, test_ids)


        train_split = SurrogateDataset(
            input_voltage=torch.from_numpy(vg1[train_rows]),
            output_voltage=torch.from_numpy(vout[train_rows]),
            process_parameters=torch.from_numpy(process_parameters[train_rows]),
            mismatch_parameters=torch.from_numpy(mismatch_parameters[train_rows]),
            vdd=torch.from_numpy(omega[train_rows, 0]),
            temperature=torch.from_numpy(omega[train_rows, 1]),
        )

        validation_split = SurrogateDataset(
            input_voltage=torch.from_numpy(vg1[validation_rows]),
            output_voltage=torch.from_numpy(vout[validation_rows]),
            process_parameters=torch.from_numpy(process_parameters[validation_rows]),
            mismatch_parameters=torch.from_numpy(mismatch_parameters[validation_rows]),
            vdd=torch.from_numpy(omega[validation_rows, 0]),
            temperature=torch.from_numpy(omega[validation_rows, 1]),
        )

        test_split = SurrogateDataset(
            input_voltage=torch.from_numpy(vg1[test_rows]),
            output_voltage=torch.from_numpy(vout[test_rows]),
            process_parameters=torch.from_numpy(process_parameters[test_rows]),
            mismatch_parameters=torch.from_numpy(mismatch_parameters[test_rows]),
            vdd=torch.from_numpy(omega[test_rows, 0]),
            temperature=torch.from_numpy(omega[test_rows, 1]),
        )
        return train_split,validation_split,test_split

    def _split_group_ids(self, group):
        """
        Shuffles the group ids with the seed and cuts them 70/20/10 into training, validation and test.

        Args:
            group: Group id of every sample, shape (n,).

        Returns:
            Tuple (train_ids, validation_ids, test_ids) of group id arrays without overlap.
        """
        # 1. Get all the unique group ids
        group_ids = np.unique(group)

        # 2. As they are probably ordered, we need to shuffle them first
        rng = np.random.default_rng(self.seed)
        group_ids = rng.permutation(group_ids)

        # 3. Now we do the actual split. As shuffling already introduced randomness, we can just cut the array of ids like we want (70/20/10)
        n_train = round(0.7 * len(group_ids))
        n_validation = round(0.2 * len(group_ids))
        train_ids = group_ids[:n_train]
        validation_ids = group_ids[n_train:n_train + n_validation]
        test_ids = group_ids[n_train + n_validation:]
        return train_ids,validation_ids,test_ids

    def _get_raw_arrays(self):
        """
        Gets the raw arrays for input voltage, output voltage, process and mismatch parameters and voltage and temperature values as well as the group ids.

        Returns:
            Tuple (vg1, vout, omega, group, process_parameters, mismatch_parameters):
                vg1, vout: Input and output voltage in V, shape (n, n_steps).
                omega: VDD in V and temperature in °C, shape (n, 2).
                group: Group id of every sample, shape (n,).
                process_parameters: Process parameters, shape (n, N_PROCESS).
                mismatch_parameters: Mismatch parameters, shape (n, N_MISMATCH).

        Raises:
            AssertionError: If an array does not have the expected shape.
        """
        dataset_path = f"../datasets/{self.name}/{self.name}_raw.npz"

        with np.load(dataset_path) as raw:
            # In a 5ms long simulation of the neuron and a measurement every microsecond, vout and vg1 have 5001 measurement points for each sample.
            # This is much more than needed. The following operations take only every 10th value and then limit the arrays to a length of 500 when using the
            # default values of this method.
            vg1 = raw["vg1"][:, ::self.step][:, :self.n_steps]
            vout = raw["vout"][:, ::self.step][:, :self.n_steps]
            theta = raw["theta"]
            omega = raw["omega"]
            group = raw["group"]
        # file closed here, the arrays stay in memory

        process_parameters = theta[:, :N_PROCESS]
        mismatch_parameters = theta[:, N_PROCESS:]

        n = len(group)
        assert vg1.shape == (n, self.n_steps)
        assert vout.shape == (n, self.n_steps)
        assert theta.shape == (n, N_PROCESS + N_MISMATCH)
        assert process_parameters.shape == (n, N_PROCESS)
        assert mismatch_parameters.shape == (n, N_MISMATCH)
        assert omega.shape == (n, N_V_T_VALUES)
        return vg1,vout,omega,group,process_parameters,mismatch_parameters


        



        






        
