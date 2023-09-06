import os, sys
import numpy as np
import argparse

import util.util_ as ut


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_dir', type=str, default='', help='')
    parser.add_argument('--input_ext', type=str, default='_hrn_high_mesh.obj', help='')
    parser.add_argument('--sampling_points', type=int, default=10000, help='')
    parser.add_argument('--output_ext', type=str, default='.npy', help='')
    parser.add_argument('--find_substring', type=str, default='', help='directory for saving results')
    
    args = parser.parse_args()
    return args


def find_files(directory, extension, sort=True):
    matching_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(extension):
                matching_files.append(os.path.join(root, file))
    if sort:
        matching_files.sort()
    return matching_files


def main(args):
    # find all files
    found_files = find_files(args.input_dir, args.input_ext)
    # print('found_files:', found_files)
    print(f'Found files {len(found_files)}\n')

    for i, input_path in enumerate(found_files):
        print(f'{i}/{len(found_files)-1}')
        print(f'input_path: {input_path}')
        pointcloud = ut.read_obj(input_path)
        if type(pointcloud) is dict and 'vertices' in pointcloud.keys():
            pointcloud = pointcloud['vertices']
        # print('pointcloud:', pointcloud)
        # print('type(pointcloud):', type(pointcloud))
        print('pointcloud.shape:', pointcloud.shape)

        sampl_pc = ut.random_select_vertices(pointcloud, args.sampling_points)
        print('sampl_pc.shape:', sampl_pc.shape)

        file_name, file_ext = input_path.split('/')[-1].split('.')
        output_dir = '/'.join(input_path.split('/')[:-1])
        output_file = file_name + '_' + str(args.sampling_points) + 'points' + args.output_ext
        output_path = os.path.join(output_dir, output_file)
        print('output_path:', output_path)

        if output_path.endswith('.obj'):
            ut.write_obj(output_path, sampl_pc)
        if output_path.endswith('.npy'):
            np.save(output_path, sampl_pc)
        print('Saved!')

        print('---------------')
        # sys.exit(0)
    
    print('\nFinished!')


if __name__ == '__main__':
    args = parse_args()
    # print('args:', args)

    main(args)