import os, sys, time
from models.hrn import Reconstructor
import cv2
from tqdm import tqdm
import argparse

# Bernardo
def find_image_files(folder_path):
    img_ext = ['.jpg', '.jpeg', '.png']
    found_files = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            # if file.lower().endswith('.jpg') or file.lower().endswith('.png'):
            file_lower = file.lower()
            for ext in img_ext:
                if file_lower.endswith(ext):
                    found_files.append(os.path.join(root, file))
                    break
    return found_files


# Bernardo
def search_save_inappropriate_files(files_paths, str_search='aaa', path_save_list='inappropriate_files.txt'):
    num_inappropriate_found = 0
    inappropriate_files = []
    inappropriate_found = False
    if len(files_paths) > 0:
        print('\nSearching inappropriate_files...')
        for i, file_path in enumerate(files_paths):
            if str_search in file_path:
                inappropriate_found = True
                num_inappropriate_found += 1
                print('Inappropriate file found:', file_path)
                inappropriate_files.append(file_path)
        
        if inappropriate_found:
            print('\nSaving inappropriate files paths')
            with open(path_save_list, 'w') as file1:
                for i, inapp_file in enumerate(inappropriate_files):
                    file1.write(inapp_file + '\n')
                    file1.flush()
    return inappropriate_found, num_inappropriate_found



def run_hrn(args):
    params = [
        '--checkpoints_dir', args.checkpoints_dir,
        '--name', args.name,
        '--epoch', args.epoch,
    ]

    reconstructor = Reconstructor(params)

    # names = sorted([name for name in os.listdir(args.input_root) if '.jpg' in name or '.png' in name or '.jpeg' in name or '.PNG' in name or '.JPG' in name or '.JPEG' in name])
    print(f'\nSearching image files in \'{args.input_root}\'...')
    names = find_image_files(args.input_root)
    # print('names:', names)
    # print('len(names):', len(names))
    # print('')
    # sys.exit(0)

    # Bernardo
    if len(names) == 0:
        raise Exception(f'No images found in \'{args.input_root}\'')

    # Bernardo
    str_search = 'render.jpg'
    path_inappropriate_list = 'inappropriate_files=' + str_search + '.txt'
    inappropriate_found, num_inappropriate_found = search_save_inappropriate_files(names, str_search, path_inappropriate_list)
    if inappropriate_found:
        raise Exception(str(num_inappropriate_found)+' inappropriate files found. List of files saved in \''+str(path_inappropriate_list)+'\'')

    if not os.path.isdir(args.output_root):
        os.makedirs(args.output_root, exist_ok=True)

    # print('predict', args.input_root)

    start_idx = 0
    if args.find_substring != '':
        for i, n in enumerate(names):
            if args.find_substring in n:
                start_idx = i
                break
    # print('start_idx:', start_idx)
    # sys.exit(0)


    # for ind, name in enumerate(tqdm(names)):              # original
    # for ind, name in enumerate(tqdm(names[start_idx:])):  # Bernardo
    for ind in range(start_idx, len(names)):                # Bernardo
        name = names[ind]                                   # Bernardo
        print(f'{ind}/{len(names)-1}')
        print('name:', name)
        # save_name = os.path.splitext(name)[0]                                         # original
        save_name = os.path.splitext(name)[0].replace(args.input_root, '').strip('/')   # Bernardo
        sub_dirs, save_name = '/'.join(save_name.split('/')[:-1]), save_name.split('/')[-1]
        print('args.output_root:', args.output_root)
        print('sub_dirs:', sub_dirs)
        print('save_name:', save_name)
        out_dir = os.path.join(args.output_root, sub_dirs, save_name)
        print('out_dir:', out_dir)
        os.makedirs(out_dir, exist_ok=True)
        img = cv2.imread(os.path.join(args.input_root, name))
        print('os.path.join(args.input_root, name):', os.path.join(args.input_root, name))

        t1 = time.time()
        output = reconstructor.predict(args, img, visualize=True, out_dir=out_dir, save_name=save_name)
        print(f'save results: {time.time() - t1} sec')
        print('----------------')
        # sys.exit(0)

    print('results are saved to:', args.output_root)


def run_mvhrn(args):
    params = [
        '--checkpoints_dir', args.checkpoints_dir,
        '--name', args.name,
        '--epoch', args.epoch,
    ]

    reconstructor = Reconstructor(params)

    names = sorted([name for name in os.listdir(args.input_root) if
                    '.jpg' in name or '.png' in name or '.jpeg' in name or '.PNG' in name or '.JPG' in name or '.JPEG' in name])
    os.makedirs(args.output_root, exist_ok=True)

    print('predict', args.input_root)

    out_dir = args.output_root
    os.makedirs(out_dir, exist_ok=True)
    img_list = []
    for ind, name in enumerate(names):
        img = cv2.imread(os.path.join(args.input_root, name))
        img_list.append(img)
        # output = reconstructor.predict_base(img, save_name=save_name, out_dir=out_dir)
    output = reconstructor.predict_multi_view(img_list, visualize=True, out_dir=out_dir)

    print('results are saved to:', args.output_root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--checkpoints_dir', type=str, default='assets/pretrained_models', help='models are saved here')
    parser.add_argument('--name', type=str, default='hrn_v1.1',
                        help='name of the experiment. It decides where to store samples and models')
    parser.add_argument('--epoch', type=str, default='10', help='which epoch to load? set to latest to use latest cached model')

    parser.add_argument('--input_type', type=str, default='single_view',  # or 'multi_view'
                        help='reconstruct from single-view or multi-view')
    parser.add_argument('--input_root', type=str, default='./assets/examples/single_view_image',
                        help='directory of input images')
    parser.add_argument('--output_root', type=str, default='./assets/examples/single_view_image_results',
                        help='directory for saving results')
    
    # Bernardo
    parser.add_argument('--find_substring', type=str, default='', help='directory for saving results')
    parser.add_argument('--no_face_align', action='store_true')
    parser.add_argument('--save_only_sampled', action='store_true')
    
    args = parser.parse_args()

    if args.input_type == 'multi_view':
        run_mvhrn(args)
    else:
        run_hrn(args)

    print('\nFinished!\n')