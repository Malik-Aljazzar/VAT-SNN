First you run gen_dataset.py locally with the following command syntax:

cd <scripts path>
gen_dataset.py plan <Name> <Groups> <Chips per Group> <MC-Seed> <Signal-Seed>

This command generates the stimuli type A to C (steps, constant and sine) and stores them as .pwl files for Cadence. It will also generate the meta.csv, groups.csv and jobs_base_stimuli.txt. All the files will be put into a newly created folder called stimuli/<Name> on the level of the parent folder this script is running in. The arguments can be understood as follows:

Name: name of the dataset
Groups: number of V/T groups
Chips/Group: number of drawn chips/instances/samples whatsoever per group
MC-Seed and Signal-Seed: are for the randomness of signals and MC simulations

Now, we need to run the simulation for the first three input types:

simulate.ps1 <Name> jobs_base_stimuli.txt [<parallel>]

Again, <Name> means the same thing. The jobs we want to run are specified in jobs_base_stimuli.txt. <parallel> is on 8 by default and defines how many spectre jobs will be running in parallel. This is how i got the dataset of 25000 simulations in 25 minutes. The simulation script first uploads gen_job.sh and psf_to_csv.py to the machine. Then it will take the entire stimuli/<Name> folder and upload it to the server location ~/stimuli/<Name>. After doing this, it will use gen_job.sh to execute every job defined in jobs_base_stimuli.txt. With status.ps1 you can monitor the status:

status.ps1 <Name>

Note that the simulate.ps1 script requires you to set up an ssh key pair beforehand and configure it in the .ssh config to be used to connect to host i83compute3 before. I recommend to read the script a bit to understand what I mean.

After that you have fetch the results. They will be located in exports/<Name> on the same level as the stimuli folder. This script also gets the mismatch and process parameters:

fetch_tar.ps1 <Name>

Based on this data, you will be able to simulate the last group too. This group has the outputs of a neuron as input (cascade). I refer to this group as group D. This will produce the jobs_cascade.txt.

gen_dataset.py kaskade <Name> <Cascades per Group> <Cascade-Seed>

Now you have to run the simulation again.

simulate.ps1 <Name> jobs_cascade.txt <parallel>

Fetch the data again.

fetch_tar.ps1 <Name>

Now you have everything u need to assemble the dataset and store it in datasets/<Name>. The relevant files are <Name>\_raw.npz and index.csv

gen_dataset.py assemble <Name>
