## 1. Generate the base stimuli (types A–C)

```powershell
gen_dataset.py plan <Name> <Groups> <Chips per Group> <MC-Seed> <Signal-Seed>
```

This command generates the stimuli of type A to C (steps, constant and sine) and stores them as `.pwl` files for Cadence. It also generates `meta.csv`, `groups.csv` and `jobs_base_stimuli.txt`. All files are put into a newly created folder `stimuli/<Name>` on the level of the parent folder this script is running in.

| Argument                 | Meaning                                                      |
| ------------------------ | ------------------------------------------------------------ |
| `Name`                   | name of the dataset                                          |
| `Groups`                 | number of V/T groups                                         |
| `Chips per Group`        | number of drawn chips/instances/samples whatsoever per group |
| `MC-Seed`, `Signal-Seed` | for the randomness of the MC simulations and the signals     |

## 2. Simulate the base stimuli

> **Note:** `simulate.ps1` requires an ssh key pair set up beforehand and configured in `~/.ssh/config` for host `i83compute3`. I recommend reading the script a bit to understand what I mean.

```powershell
simulate.ps1 <Name> jobs_base_stimuli.txt [<parallel>]
```

`<Name>` means the same thing as above. The jobs to run are specified in `jobs_base_stimuli.txt`. `<parallel>` is 8 by default and defines how many Spectre jobs run in parallel. This is how I got the dataset of 25000 simulations in 25 minutes.

The script

1. uploads `gen_job.sh` and `psf_to_csv.py` to the machine,
2. uploads the entire `stimuli/<Name>` folder to `~/stimuli/<Name>` on the server,
3. runs every job defined in `jobs_base_stimuli.txt` with `gen_job.sh`.

You can also monitor the status.

```powershell
status.ps1 <Name>
```

## 3. Fetch the results

```powershell
fetch_tar.ps1 <Name>
```

The results are located in `exports/<Name>` on the same level as the `stimuli` folder. This script also gets the mismatch and process parameters.

## 4. Generate the cascade stimuli (type D)

Based on this data you can simulate the last group too. This group has the outputs of a neuron as input (cascade); I refer to it as group D. This produces `jobs_cascade.txt`.

```powershell
gen_dataset.py cascade <Name> <Cascades per Group> <Cascade-Seed>
```

## 5. Simulate and fetch the cascade

Run the simulation again and fetch the data again.

```powershell
simulate.ps1 <Name> jobs_cascade.txt [<parallel>]
fetch_tar.ps1 <Name>
```

## 6. Assemble the dataset

```powershell
gen_dataset.py assemble <Name>
```

Now you have everything you need to assemble the dataset. It is stored in `datasets/<Name>`; the relevant files are `<Name>_raw.npz` and `index.csv`.
