# CUDA = 11.6
# Python = 3.9
# PyTorch = 1.13.0
# torchvision = 0.14.0
# pytorch-cuda = 11.6
# fvcore = 0.1.5.post20221221
# iopath = 0.1.9
# pytorch3d = 0.7.4


# CREATE CONDA ENV
# CONDA_ENV=/home/bjgbiesseck/anaconda3/envs/BOVIFOCR_HRN_py39
CONDA_ENV=BOVIFOCR_HRN_py39
# conda create --prefix $CONDA_ENV python=3.9
conda create -y --name $CONDA_ENV python=3.9
conda activate $CONDA_ENV

export CUDA_HOME=/usr/local/cuda-11.6
export LD_LIBRARY_PATH=$CUDA_HOME/lib64
export PATH=$CUDA_HOME:$CUDA_HOME/bin:$LD_LIBRARY_PATH:$PATH

conda install -y pytorch=1.13.0 torchvision pytorch-cuda=11.6 -c pytorch -c nvidia
conda install -y -c fvcore -c iopath -c conda-forge fvcore iopath
conda install -y -c bottler nvidiacub
conda install -y pytorch3d -c pytorch3d


# CLONE REPO
cd ~
git clone https://github.com/BOVIFOCR/HRN_3D_face_reconstruction.git
cd HRN_3D_face_reconstruction


# INSTALL REQUIREMENTS WITH PIP
pip install -r requirements.txt
pip install typing-extensions --upgrade


# INSTALL nvdiffrast
git clone https://github.com/NVlabs/nvdiffrast.git
cd nvdiffrast
pip install .
cd ..


# INSTALL DEPENDENCIES
apt-get install freeglut3-dev
apt-get install binutils-gold g++ cmake libglew-dev mesa-common-dev build-essential libglew1.5-dev libglm-dev
apt-get install mesa-utils
apt-get install libegl1-mesa-dev 
apt-get install libgles2-mesa-dev
# apt-get install libnvidia-gl-525  (TAKE CARE, this may change the GPU driver)


# DOWNLOAD FOLDERS '3dmm_assets' AND 'pretrained_models' AND PUT THEM INTO 'assets' folder
# LINK: https://drive.google.com/drive/folders/1qI3-5GKxEDbQBSUCwDWmH15uWU3Ka5LS


# RUN TEST CODE
CUDA_VISIBLE_DEVICES=0 python demo.py --input_type single_view --input_root ./assets/examples/single_view_image --output_root ./assets/examples/single_view_image_results


