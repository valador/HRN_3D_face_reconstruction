import cv2
import numpy as np
import time
from PIL import Image
import os
from facelandmark.large_model_infer import LargeModelInfer
import torch
from models import create_model
from options.test_options import TestOptions
from util.load_mats import load_lm3d
from util.preprocess import align_img, estimate_norm, align_for_lm
import PIL.Image
from util.util_ import resize_on_long_side, split_vis
import face_alignment
import tensorflow as tf


if tf.__version__ >= '2.0':
    tf = tf.compat.v1
    tf.disable_eager_execution()


class Reconstructor():
    def __init__(self, params):
        opt = TestOptions().parse(params)
        self.phase = opt.phase
        self.face_mark_model = LargeModelInfer("assets/pretrained_models/large_base_net.pth", device='cuda')

        device = torch.device(0)
        torch.cuda.set_device(device)
        self.model = create_model(opt)
        self.model.setup(opt)
        self.model.device = device
        self.model.parallelize()
        self.model.eval()
        self.model.set_render(opt, image_res=512)

        # self.lm_sess = face_alignment.FaceAlignment(face_alignment.LandmarksType._3D, flip_input=False)    # original
        self.lm_sess = face_alignment.FaceAlignment(face_alignment.LandmarksType.THREE_D, flip_input=False)  # Bernardo

        config = tf.ConfigProto(allow_soft_placement=True)
        config.gpu_options.per_process_gpu_memory_fraction = 0.2
        config.gpu_options.allow_growth = True
        g1 = tf.Graph()
        self.face_sess = tf.Session(graph=g1, config=config)
        with self.face_sess.as_default():
            with g1.as_default():
                with tf.gfile.FastGFile('assets/pretrained_models/segment_face.pb', 'rb') as f:
                    graph_def = tf.GraphDef()
                    graph_def.ParseFromString(f.read())
                    self.face_sess.graph.as_default()
                    tf.import_graph_def(graph_def, name='')
                    self.face_sess.run(tf.global_variables_initializer())

        self.lm3d_std = load_lm3d(opt.bfm_folder)

    def read_data(self, img, lm, lm3d_std, to_tensor=True, image_res=1024, img_fat=None):
        # to RGB
        im = PIL.Image.fromarray(img[..., ::-1])
        W, H = im.size
        lm[:, -1] = H - 1 - lm[:, -1]
        _, im_lr, lm_lr, _ = align_img(im, lm, lm3d_std)
        _, im_hd, lm_hd, _ = align_img(im, lm, lm3d_std, target_size=image_res, rescale_factor=102. * image_res / 224)
        if img_fat is not None:
            assert img_fat.shape == img.shape
            im_fat = PIL.Image.fromarray(img_fat[..., ::-1])
            _, im_hd, _, _ = align_img(im_fat, lm, lm3d_std, target_size=image_res, rescale_factor=102. * image_res / 224)

        mask_lr = self.face_sess.run(self.face_sess.graph.get_tensor_by_name('output_alpha:0'), feed_dict={'input_image:0': np.array(im_lr)})

        # im_hd = np.array(im_hd).astype(np.float32)
        if to_tensor:
            im_lr = torch.tensor(np.array(im_lr) / 255., dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)
            im_hd = torch.tensor(np.array(im_hd) / 255., dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)
            mask_lr = torch.tensor(np.array(mask_lr) / 255., dtype=torch.float32)[None, None, :, :]
            lm_lr = torch.tensor(lm_lr).unsqueeze(0)
            lm_hd = torch.tensor(lm_hd).unsqueeze(0)
        return im_lr, lm_lr, im_hd, lm_hd, mask_lr

    def parse_label(self, label):
        return torch.tensor(np.array(label).astype(np.float32))

    def prepare_data(self, img, lm_sess, five_points=None):
        input_img, scale, bbox = align_for_lm(img, five_points)  # align for 68 landmark detection

        if scale == 0:
            return None

        # detect landmarks
        input_img = np.reshape(
            input_img, [1, 224, 224, 3]).astype(np.float32)

        input_img = input_img[0, :, :, ::-1]
        # landmark = lm_sess.get_landmarks_from_image(input_img)[0]   # original
        landmark = lm_sess.get_landmarks_from_image(input_img)        # Bernardo

        if not landmark is None:
            landmark = landmark[0]
            landmark = landmark[:, :2] / scale
            landmark[:, 0] = landmark[:, 0] + bbox[0]
            landmark[:, 1] = landmark[:, 1] + bbox[1]

            # t1 = time.time()
            # att_mask = skinmask(img)
            # att_mask = PIL.Image.fromarray(cv2.cvtColor(att_mask,cv2.COLOR_BGR2RGB))
            # print('get att_mask', time.time() - t1)

        else:
            # 68 landmarks (Bernardo)
            landmark = np.array([[  8.741072,  38.3125  ],
                                 [ 11.5625,    48.89286 ],
                                 [ 14.38393,   58.0625  ],
                                 [ 19.32143,   66.52679 ],
                                 [ 22.142857,  78.51786 ],
                                 [ 27.785713,  89.09821 ],
                                 [ 35.544643,  97.5625  ],
                                 [ 44.008926, 106.73215 ],
                                 [ 57.410713, 110.96429 ],
                                 [ 69.40179,  105.32143 ],
                                 [ 76.45536,   97.5625  ],
                                 [ 82.80357,   89.09821 ],
                                 [ 87.03571,   78.51786 ],
                                 [ 89.85715,   67.9375  ],
                                 [ 92.67857,   58.0625  ],
                                 [ 94.08929,   47.482143],
                                 [ 96.20536,   36.901787],
                                 [ 20.732143,  38.3125  ],
                                 [ 26.375,     35.491074],
                                 [ 32.723213,  35.491074],
                                 [ 39.776787,  38.3125  ],
                                 [ 45.41964,   40.428574],
                                 [ 67.99107,   40.428574],
                                 [ 72.22321,   36.901787],
                                 [ 77.86607,   34.080357],
                                 [ 85.625,     34.080357],
                                 [ 89.85715,   35.491074],
                                 [ 56.,        55.241074],
                                 [ 56.,        63.70536 ],
                                 [ 56.,        71.46429 ],
                                 [ 56.,        77.10715 ],
                                 [ 48.946426,  77.10715 ],
                                 [ 53.178574,  78.51786 ],
                                 [ 57.410713,  79.92857 ],
                                 [ 60.23214,   78.51786 ],
                                 [ 65.16965,   77.10715 ],
                                 [ 29.19643,   50.303574],
                                 [ 34.13393,   48.89286 ],
                                 [ 39.776787,  48.89286 ],
                                 [ 44.008926,  51.714287],
                                 [ 39.776787,  53.125   ],
                                 [ 34.13393,   53.125   ],
                                 [ 67.99107,   51.714287],
                                 [ 72.22321,   48.89286 ],
                                 [ 77.86607,   48.89286 ],
                                 [ 82.80357,   50.303574],
                                 [ 77.86607,   53.125   ],
                                 [ 72.22321,   53.125   ],
                                 [ 41.1875,    87.6875  ],
                                 [ 45.41964,   87.6875  ],
                                 [ 53.178574,  86.27679 ],
                                 [ 57.410713,  86.27679 ],
                                 [ 60.23214,   86.27679 ],
                                 [ 67.99107,   86.27679 ],
                                 [ 72.22321,   86.27679 ],
                                 [ 67.99107,   93.33036 ],
                                 [ 61.64286,   96.15179 ],
                                 [ 57.410713,  97.5625  ],
                                 [ 51.76786,   97.5625  ],
                                 [ 46.83036,   93.33036 ],
                                 [ 42.598213,  87.6875  ],
                                 [ 51.76786,   89.09821 ],
                                 [ 57.410713,  89.09821 ],
                                 [ 61.64286,   89.09821 ],
                                 [ 70.8125,    86.27679 ],
                                 [ 61.64286,   91.91965 ],
                                 [ 57.410713,  91.91965 ],
                                 [ 51.76786,   91.91965 ]], dtype=float)
            
            '''
            # Bernardo: draw landmarks in image
            img_copy = img.copy()
            for ldmk in landmark:
                x, y = ldmk
                cv2.circle(img_copy, (int(round(x)), int(round(y))), 1, (0, 255, 0), 1)  # Draw a green circle at each landmark
            # Save the image with landmarks drawn
            save_path = '/datasets1/bjgbiesseck/MS-Celeb-1M/ms1m-retinaface-t1/3D_reconstruction/HRN/images/m.05xdp5/65-FaceId-2/face_with_landmarks.png'
            cv2.imwrite(save_path, img_copy)

            import sys
            sys.exit(0)
            '''

        return landmark

    def get_img_for_texture(self, input_img_tensor):
        input_img = input_img_tensor.permute(0, 2, 3, 1).detach().cpu().numpy()[0] * 255.
        input_img = input_img.astype(np.uint8)

        input_img_for_texture = self.face_mark_model.fat_face(input_img, degree=0.03)
        input_img_for_texture_tensor = torch.tensor(np.array(input_img_for_texture) / 255., dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)
        input_img_for_texture_tensor = input_img_for_texture_tensor.to(self.model.device)
        return input_img_for_texture_tensor

    # Bernardo
    def get_img_for_texture_no_face_detection(self, input_img_tensor):
        input_img = input_img_tensor.permute(0, 2, 3, 1).detach().cpu().numpy()[0] * 255.
        input_img = input_img.astype(np.uint8)

        # input_img_for_texture = self.face_mark_model.fat_face(input_img, degree=0.03)
        input_img_for_texture = input_img
        input_img_for_texture_tensor = torch.tensor(np.array(input_img_for_texture) / 255., dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)
        input_img_for_texture_tensor = input_img_for_texture_tensor.to(self.model.device)
        return input_img_for_texture_tensor

    def predict_base(self, img, out_dir=None, save_name=''):

        timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        if save_name != '':
            img_name = save_name
        else:
            img_name = 'face-reconstruction_' + timestamp

        # img_ori = img.copy()
        if img.shape[0] > 2000 or img.shape[1] > 2000:
            img, _ = resize_on_long_side(img, 1500)

        # if out_dir is not None:
        #     img_path = os.path.join(out_dir, img_name + '_img.jpg')
        #     cv2.imwrite(img_path, img)

        box, results = self.face_mark_model.infer(img)

        if results is None or np.array(results).shape[0] == 0:
            return {}

        # t1 = time.time()
        # fatbgr = self.face_mark_model.fat_face(img, degree=0.005)
        # print('-' * 50, 'fat face', time.time() - t1)
        fatbgr = None

        landmarks = []
        results = results[0]
        for idx in [74, 83, 54, 84, 90]:
            landmarks.append([results[idx][0], results[idx][1]])
        landmarks = np.array(landmarks)

        landmarks = self.prepare_data(img, self.lm_sess, five_points=landmarks)

        im_tensor, lm_tensor, im_hd_tensor, lm_hd_tensor, mask = self.read_data(img, landmarks, self.lm3d_std, image_res=512, img_fat=fatbgr)
        # M = estimate_norm(lm_tensor.numpy()[0], im_tensor.shape[2])
        # M_tensor = self.parse_label(M)[None, ...]
        data = {
            'imgs': im_tensor,
            'imgs_hd': im_hd_tensor,
            'lms': lm_tensor,
            'lms_hd': lm_hd_tensor,
            # 'M': M_tensor,
            # 'msks': att_mask,
            'img_name': img_name,
            'face_mask': mask,
        }
        self.model.set_input_base(data)  # unpack data from data loader

        output = self.model.predict_results_base()  # run inference

        if out_dir is not None:
            t1 = time.time()

            # save texture map
            tex_map = (output['texture_map'][0] * 255.0).detach().cpu().numpy()[..., ::-1]
            cv2.imwrite(os.path.join(out_dir, img_name + '_texOri.jpg'), tex_map)

            # t2 = time.time()
            # # save mesh
            # color_map = (output['color_map'].permute(0, 2, 3, 1)[0] * 255.0).detach().cpu().numpy()
            # color_map = color_map[..., ::-1].clip(0, 255)
            # face_mesh = {
            #     'vertices': output['vertices'][0].detach().cpu().numpy(),
            #     'faces': output['triangles'] + 1,
            #     'UVs': output['UVs'],
            #     'texture_map': color_map
            # }
            # write_obj2(os.path.join(out_dir, img_name + '.obj'), mesh=face_mesh)
            # print('save mesh', time.time() - t2)

            # save coefficients
            coeffs = output['coeffs'].detach().cpu().numpy()  # (1, 257)
            np.save(os.path.join(out_dir, img_name + '_coeffs'), coeffs)

            # # save albedo map
            # albedo_map = (output['albedo_map'].permute(0, 2, 3, 1)[0] * 255.0).detach().cpu().numpy()
            # albedo_map = albedo_map[..., ::-1]
            # cv2.imwrite(os.path.join(out_dir, img_name + '_albedo_map.jpg'), albedo_map)

            # save position map
            position_map = output['position_map'].detach().cpu().numpy()  # (1, 3, h, w)
            np.save(os.path.join(out_dir, img_name + '_position_map'), position_map)
            position_map_vis = position_map.transpose(0, 2, 3, 1)[0, ..., ::-1]
            position_map_vis = 255.0 * (position_map_vis - position_map_vis.min()) / (position_map_vis.max() - position_map_vis.min())
            cv2.imwrite(os.path.join(out_dir, img_name + '_position_map_vis.jpg'), position_map_vis)

            # save input face
            input_face = output['input_face']
            cv2.imwrite(os.path.join(out_dir, img_name + '_01_input_face.jpg'), input_face)

            # save pred face
            pred_face = output['pred_face']
            cv2.imwrite(os.path.join(out_dir, img_name + '_02_pred_face.jpg'), pred_face)

            # save input face hd
            input_face_hd = output['input_face_hd']
            cv2.imwrite(os.path.join(out_dir, img_name + '_03_input_face_hd.jpg'), input_face_hd)

            # save gt lms
            gt_lm = output['gt_lm'].detach().cpu().numpy()  # (1, 68, 2)
            np.save(os.path.join(out_dir, img_name + '_lmks'), gt_lm)

            # save face mask
            face_mask = (output['face_mask'][0, 0] * 255.0).detach().cpu().numpy()
            cv2.imwrite(os.path.join(out_dir, img_name + '_face_mask.jpg'), face_mask)

            # save tex valid mask
            face_mask = (output['tex_valid_mask'][0, 0] * 255.0).detach().cpu().numpy()
            cv2.imwrite(os.path.join(out_dir, img_name + '_tex_valid_mask.jpg'), face_mask)

            # save de-retouched albedo map
            de_retouched_albedo_map = (output['de_retouched_albedo_map'].permute(0, 2, 3, 1)[0] * 255.0).detach().cpu().numpy()
            de_retouched_albedo_map = de_retouched_albedo_map[..., ::-1]
            cv2.imwrite(os.path.join(out_dir, img_name + '_de_retouched_albedo_map.jpg'), de_retouched_albedo_map)

            # print('save results', time.time() - t1)

        return output


    # Bernardo
    def predict_base_no_face_detection(self, img, out_dir=None, save_name=''):

        timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        if save_name != '':
            img_name = save_name
        else:
            img_name = 'face-reconstruction_' + timestamp

        # img_ori = img.copy()
        if img.shape[0] > 2000 or img.shape[1] > 2000:
            img, _ = resize_on_long_side(img, 1500)

        # if out_dir is not None:
        #     img_path = os.path.join(out_dir, img_name + '_img.jpg')
        #     cv2.imwrite(img_path, img)

        '''
        box, results = self.face_mark_model.infer(img)
        '''

        '''
        if results is None or np.array(results).shape[0] == 0:
            return {}
        '''

        # t1 = time.time()
        # fatbgr = self.face_mark_model.fat_face(img, degree=0.005)
        # print('-' * 50, 'fat face', time.time() - t1)
        fatbgr = None

        '''
        landmarks = []
        results = results[0]
        for idx in [74, 83, 54, 84, 90]:
            landmarks.append([results[idx][0], results[idx][1]])
        landmarks = np.array(landmarks)
        '''

        # Bernardo
        landmarks_percent_face_not_det = np.array([[0.341916071428571, 0.461574107142857],
                                                   [0.656533928571429, 0.459833928571429],
                                                   [0.500225,          0.640505357142857],
                                                   [0.370975892857143, 0.824691964285714],
                                                   [0.631516964285714, 0.823250892857143]], dtype=np.float32)
        landmarks_coords_face_not_det = np.zeros((landmarks_percent_face_not_det.shape), dtype=int)
        landmarks_coords_face_not_det[:,0] = landmarks_percent_face_not_det[:,0] * img.shape[1]
        landmarks_coords_face_not_det[:,1] = landmarks_percent_face_not_det[:,1] * img.shape[0]
        landmarks = landmarks_coords_face_not_det.astype(int)

        landmarks = self.prepare_data(img, self.lm_sess, five_points=landmarks)

        im_tensor, lm_tensor, im_hd_tensor, lm_hd_tensor, mask = self.read_data(img, landmarks, self.lm3d_std, image_res=512, img_fat=fatbgr)
        # M = estimate_norm(lm_tensor.numpy()[0], im_tensor.shape[2])
        # M_tensor = self.parse_label(M)[None, ...]
        data = {
            'imgs': im_tensor,
            'imgs_hd': im_hd_tensor,
            'lms': lm_tensor,
            'lms_hd': lm_hd_tensor,
            # 'M': M_tensor,
            # 'msks': att_mask,
            'img_name': img_name,
            'face_mask': mask,
        }
        self.model.set_input_base(data)  # unpack data from data loader

        output = self.model.predict_results_base()  # run inference

        if out_dir is not None:
            t1 = time.time()

            # save texture map
            tex_map = (output['texture_map'][0] * 255.0).detach().cpu().numpy()[..., ::-1]
            cv2.imwrite(os.path.join(out_dir, img_name + '_texOri.jpg'), tex_map)

            # t2 = time.time()
            # # save mesh
            # color_map = (output['color_map'].permute(0, 2, 3, 1)[0] * 255.0).detach().cpu().numpy()
            # color_map = color_map[..., ::-1].clip(0, 255)
            # face_mesh = {
            #     'vertices': output['vertices'][0].detach().cpu().numpy(),
            #     'faces': output['triangles'] + 1,
            #     'UVs': output['UVs'],
            #     'texture_map': color_map
            # }
            # write_obj2(os.path.join(out_dir, img_name + '.obj'), mesh=face_mesh)
            # print('save mesh', time.time() - t2)

            # save coefficients
            coeffs = output['coeffs'].detach().cpu().numpy()  # (1, 257)
            np.save(os.path.join(out_dir, img_name + '_coeffs'), coeffs)

            # # save albedo map
            # albedo_map = (output['albedo_map'].permute(0, 2, 3, 1)[0] * 255.0).detach().cpu().numpy()
            # albedo_map = albedo_map[..., ::-1]
            # cv2.imwrite(os.path.join(out_dir, img_name + '_albedo_map.jpg'), albedo_map)

            # save position map
            position_map = output['position_map'].detach().cpu().numpy()  # (1, 3, h, w)
            np.save(os.path.join(out_dir, img_name + '_position_map'), position_map)
            position_map_vis = position_map.transpose(0, 2, 3, 1)[0, ..., ::-1]
            position_map_vis = 255.0 * (position_map_vis - position_map_vis.min()) / (position_map_vis.max() - position_map_vis.min())
            cv2.imwrite(os.path.join(out_dir, img_name + '_position_map_vis.jpg'), position_map_vis)

            # save input face
            input_face = output['input_face']
            cv2.imwrite(os.path.join(out_dir, img_name + '_01_input_face.jpg'), input_face)

            # save pred face
            pred_face = output['pred_face']
            cv2.imwrite(os.path.join(out_dir, img_name + '_02_pred_face.jpg'), pred_face)

            # save input face hd
            input_face_hd = output['input_face_hd']
            cv2.imwrite(os.path.join(out_dir, img_name + '_03_input_face_hd.jpg'), input_face_hd)

            # save gt lms
            gt_lm = output['gt_lm'].detach().cpu().numpy()  # (1, 68, 2)
            np.save(os.path.join(out_dir, img_name + '_lmks'), gt_lm)

            # save face mask
            face_mask = (output['face_mask'][0, 0] * 255.0).detach().cpu().numpy()
            cv2.imwrite(os.path.join(out_dir, img_name + '_face_mask.jpg'), face_mask)

            # save tex valid mask
            face_mask = (output['tex_valid_mask'][0, 0] * 255.0).detach().cpu().numpy()
            cv2.imwrite(os.path.join(out_dir, img_name + '_tex_valid_mask.jpg'), face_mask)

            # save de-retouched albedo map
            de_retouched_albedo_map = (output['de_retouched_albedo_map'].permute(0, 2, 3, 1)[0] * 255.0).detach().cpu().numpy()
            de_retouched_albedo_map = de_retouched_albedo_map[..., ::-1]
            cv2.imwrite(os.path.join(out_dir, img_name + '_de_retouched_albedo_map.jpg'), de_retouched_albedo_map)

            # print('save results', time.time() - t1)

        return output
    

    # Bernardo
    def predict_base_no_face_detection_save_only_sampled(self, img, out_dir=None, save_name=''):

        timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        if save_name != '':
            img_name = save_name
        else:
            img_name = 'face-reconstruction_' + timestamp

        # img_ori = img.copy()
        if img.shape[0] > 2000 or img.shape[1] > 2000:
            img, _ = resize_on_long_side(img, 1500)

        # if out_dir is not None:
        #     img_path = os.path.join(out_dir, img_name + '_img.jpg')
        #     cv2.imwrite(img_path, img)

        '''
        box, results = self.face_mark_model.infer(img)
        '''

        '''
        if results is None or np.array(results).shape[0] == 0:
            return {}
        '''

        # t1 = time.time()
        # fatbgr = self.face_mark_model.fat_face(img, degree=0.005)
        # print('-' * 50, 'fat face', time.time() - t1)
        fatbgr = None

        '''
        landmarks = []
        results = results[0]
        for idx in [74, 83, 54, 84, 90]:
            landmarks.append([results[idx][0], results[idx][1]])
        landmarks = np.array(landmarks)
        '''

        # Bernardo
        landmarks_percent_face_not_det = np.array([[0.341916071428571, 0.461574107142857],
                                                   [0.656533928571429, 0.459833928571429],
                                                   [0.500225,          0.640505357142857],
                                                   [0.370975892857143, 0.824691964285714],
                                                   [0.631516964285714, 0.823250892857143]], dtype=np.float32)
        landmarks_coords_face_not_det = np.zeros((landmarks_percent_face_not_det.shape), dtype=int)
        landmarks_coords_face_not_det[:,0] = landmarks_percent_face_not_det[:,0] * img.shape[1]
        landmarks_coords_face_not_det[:,1] = landmarks_percent_face_not_det[:,1] * img.shape[0]
        landmarks = landmarks_coords_face_not_det.astype(int)

        landmarks = self.prepare_data(img, self.lm_sess, five_points=landmarks)

        im_tensor, lm_tensor, im_hd_tensor, lm_hd_tensor, mask = self.read_data(img, landmarks, self.lm3d_std, image_res=512, img_fat=fatbgr)
        # M = estimate_norm(lm_tensor.numpy()[0], im_tensor.shape[2])
        # M_tensor = self.parse_label(M)[None, ...]
        data = {
            'imgs': im_tensor,
            'imgs_hd': im_hd_tensor,
            'lms': lm_tensor,
            'lms_hd': lm_hd_tensor,
            # 'M': M_tensor,
            # 'msks': att_mask,
            'img_name': img_name,
            'face_mask': mask,
        }
        self.model.set_input_base(data)  # unpack data from data loader

        output = self.model.predict_results_base()  # run inference

        '''
        if out_dir is not None:
            t1 = time.time()

            # save texture map
            tex_map = (output['texture_map'][0] * 255.0).detach().cpu().numpy()[..., ::-1]
            cv2.imwrite(os.path.join(out_dir, img_name + '_texOri.jpg'), tex_map)

            # t2 = time.time()
            # # save mesh
            # color_map = (output['color_map'].permute(0, 2, 3, 1)[0] * 255.0).detach().cpu().numpy()
            # color_map = color_map[..., ::-1].clip(0, 255)
            # face_mesh = {
            #     'vertices': output['vertices'][0].detach().cpu().numpy(),
            #     'faces': output['triangles'] + 1,
            #     'UVs': output['UVs'],
            #     'texture_map': color_map
            # }
            # write_obj2(os.path.join(out_dir, img_name + '.obj'), mesh=face_mesh)
            # print('save mesh', time.time() - t2)

            # save coefficients
            coeffs = output['coeffs'].detach().cpu().numpy()  # (1, 257)
            np.save(os.path.join(out_dir, img_name + '_coeffs'), coeffs)

            # # save albedo map
            # albedo_map = (output['albedo_map'].permute(0, 2, 3, 1)[0] * 255.0).detach().cpu().numpy()
            # albedo_map = albedo_map[..., ::-1]
            # cv2.imwrite(os.path.join(out_dir, img_name + '_albedo_map.jpg'), albedo_map)

            # save position map
            position_map = output['position_map'].detach().cpu().numpy()  # (1, 3, h, w)
            np.save(os.path.join(out_dir, img_name + '_position_map'), position_map)
            position_map_vis = position_map.transpose(0, 2, 3, 1)[0, ..., ::-1]
            position_map_vis = 255.0 * (position_map_vis - position_map_vis.min()) / (position_map_vis.max() - position_map_vis.min())
            cv2.imwrite(os.path.join(out_dir, img_name + '_position_map_vis.jpg'), position_map_vis)

            # save input face
            input_face = output['input_face']
            cv2.imwrite(os.path.join(out_dir, img_name + '_01_input_face.jpg'), input_face)

            # save pred face
            pred_face = output['pred_face']
            cv2.imwrite(os.path.join(out_dir, img_name + '_02_pred_face.jpg'), pred_face)

            # save input face hd
            input_face_hd = output['input_face_hd']
            cv2.imwrite(os.path.join(out_dir, img_name + '_03_input_face_hd.jpg'), input_face_hd)

            # save gt lms
            gt_lm = output['gt_lm'].detach().cpu().numpy()  # (1, 68, 2)
            np.save(os.path.join(out_dir, img_name + '_lmks'), gt_lm)

            # save face mask
            face_mask = (output['face_mask'][0, 0] * 255.0).detach().cpu().numpy()
            cv2.imwrite(os.path.join(out_dir, img_name + '_face_mask.jpg'), face_mask)

            # save tex valid mask
            face_mask = (output['tex_valid_mask'][0, 0] * 255.0).detach().cpu().numpy()
            cv2.imwrite(os.path.join(out_dir, img_name + '_tex_valid_mask.jpg'), face_mask)

            # save de-retouched albedo map
            de_retouched_albedo_map = (output['de_retouched_albedo_map'].permute(0, 2, 3, 1)[0] * 255.0).detach().cpu().numpy()
            de_retouched_albedo_map = de_retouched_albedo_map[..., ::-1]
            cv2.imwrite(os.path.join(out_dir, img_name + '_de_retouched_albedo_map.jpg'), de_retouched_albedo_map)

            # print('save results', time.time() - t1)
        '''

        return output


    def predict(self, args, img, visualize=False, out_dir=None, save_name=''):
        with torch.no_grad():

            # Bernardo
            if not hasattr(args, 'no_face_align') or not args.no_face_align:
                # output = self.predict_base(img)                                            # original
                output = self.predict_base(img, out_dir, save_name)                          # Bernardo
                output['input_img_for_tex'] = self.get_img_for_texture(output['input_img'])  # original
            else:
                if not args.save_only_sampled:
                    output = self.predict_base_no_face_detection(img, out_dir, save_name)                      # Bernardo
                else:
                    output = self.predict_base_no_face_detection_save_only_sampled(img, out_dir, save_name)    # Bernardo
                output['input_img_for_tex'] = self.get_img_for_texture_no_face_detection(output['input_img'])  # Bernardo

            hrn_input = {
                'input_img': output['input_img'],
                'input_img_for_tex': output['input_img_for_tex'],
                'input_img_hd': output['input_img_hd'],
                'face_mask': output['face_mask'],
                'gt_lm': output['gt_lm'],
                'coeffs': output['coeffs'],
                'position_map': output['position_map'],
                'texture_map': output['texture_map'],
                'tex_valid_mask': output['tex_valid_mask'],
                'de_retouched_albedo_map': output['de_retouched_albedo_map']
            }

            self.model.set_input_hrn(hrn_input)
            self.model.get_edge_points_horizontal()

            self.model.forward_hrn(visualize=visualize)

            output['deformation_map'] = self.model.deformation_map
            output['displacement_map'] = self.model.displacement_map

            if out_dir is not None:
                if args.save_only_sampled:   # Bernardo
                    results = self.model.save_results_only_sampled(out_dir, save_name)
                else:
                    results = self.model.save_results(out_dir, save_name)
                output['hrn_output_vis'] = results['output_vis']

        return output

    def predict_multi_view(self, img_list, visualize=False, out_dir=None, save_name='test'):
        with torch.no_grad():
            output = {}
            self.model.init_mvhrn_input()
            for ind, img in enumerate(img_list):
                hrn_model_output = self.predict(img, visualize=visualize)
                output['view_{}'.format(ind+1)] = hrn_model_output

                mv_hrn_input = {
                    'input_img': hrn_model_output['input_img'],
                    'input_img_for_tex': hrn_model_output['input_img_for_tex'],
                    'input_img_hd': hrn_model_output['input_img_hd'],
                    'face_mask': hrn_model_output['face_mask'],
                    'gt_lm': hrn_model_output['gt_lm'],
                    'coeffs': hrn_model_output['coeffs'],
                    'position_map': hrn_model_output['position_map'],
                    'texture_map': hrn_model_output['texture_map'],
                    'tex_valid_mask': hrn_model_output['tex_valid_mask'],
                    'de_retouched_albedo_map': hrn_model_output['de_retouched_albedo_map'],
                    'deformation_map': hrn_model_output['deformation_map'],
                    'displacement_map': hrn_model_output['displacement_map'],
                }

                self.model.add_input_mvhrn(mv_hrn_input)

            self.model.get_edge_points_horizontal_list()

            self.model.forward_mvhrn(visualize=visualize)

            output['canonical_deformation_map'] = self.model.canonical_deformation_map
            output['displacement_map_list'] = self.model.displacement_map_list

            if out_dir is not None:
                t1 = time.time()
                results = self.model.save_results_mvhrn(out_dir, save_name)
                print('save results', time.time() - t1)
                output['hrn_output_vis'] = results

        return output
