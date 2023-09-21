import os
import numpy as np
import sys


def get_subfolders(folder_path):
    for root, dirs, files in os.walk(folder_path):
        return dirs


def make_symbolic_links_folders(src_path='', folders_names=[''], limit_folders=10, dst_path=''):
    assert len(folders_names) >= limit_folders
    assert os.path.exists(src_path)
    if not os.path.exists(dst_path):
        print('Making destination folder \'' + dst_path + '\' ...')
        os.makedirs(dst_path)

    print('Making symbolic links in \'' + dst_path + '\' ...')
    for i, folder_name in enumerate(folders_names[:limit_folders]):
        src_folder_path = src_path + '/' + folder_name
        dst_folder_path = dst_path + '/' + folder_name
        command = 'ln -s ' + src_folder_path + ' ' + dst_folder_path
        print('%d/%d - %s' % (i+1, limit_folders, dst_folder_path), end='\r')
        os.system(command)
    print()



if __name__ == '__main__':
    src_path = '/datasets1/bjgbiesseck/MS-Celeb-1M/ms1m-retinaface-t1/3D_reconstruction/HRN/images'   # duo

    tgt_path = '/datasets1/bjgbiesseck/MS-Celeb-1M/ms1m-retinaface-t1/3D_reconstruction/HRN'          # duo

    
    # nums_subjects_symb_links = [1000]
    nums_subjects_symb_links = [2000, 5000]
    # nums_subjects_symb_links = [1000, 2000, 5000]
    # nums_subjects_symb_links = [1000, 2000, 5000, 10000]


    print('Searching all subfolders in \'' + src_path + '\' ...')
    subfolders_list = get_subfolders(src_path)
    # print('subfolders_list:', subfolders_list)
    print('len(subfolders_list):', len(subfolders_list))

    tgt_folder_name = src_path.split('/')[-1]
    for num_subjects in nums_subjects_symb_links:
        # path_target_symb_links = '/'.join(src_path.split('/')[:-1]) + '/images_' + str(num_subjects) + 'subj'
        path_target_symb_links = os.path.join(tgt_path, tgt_folder_name+str(num_subjects)+'subj')
        print('\nMaking %s symbolic links...' % (num_subjects))
        make_symbolic_links_folders(src_path, subfolders_list, num_subjects, path_target_symb_links)

