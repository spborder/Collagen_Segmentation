"""

Collagen segmentation prediction pipeline for WSI input


"""

from typing import Type
import torch
from torch.utils.data import DataLoader
import segmentation_models_pytorch as smp

from tqdm import tqdm
import os
import numpy as np
from glob import glob

import matplotlib.pyplot as plt
from PIL import Image
import pandas as pd

import neptune.new as neptune

import datetime

def Test_Network(model_path,test_dataset,test_parameters):

    device = torch.device('cuda') if torch.cuda.is_available() else 'cpu'
    output_dir = test_parameters['output_dir']

    if test_parameters['target_type']=='binary':
        n_classes = 2
    else:
        n_classes = 1

    model = smp.UnetPlusPlus(
        encoder_name = test_parameters['encoder'],
        encoder_weights = test_parameters['encoder_weights'],
        in_channels = 3,
        classes = n_classes,
        activation = test_parameters['active']
    )

    model.load_state_dict(torch.load(model_path))
    model.to(device)
    model.eval()

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with torch.no_grad():

        test_dataloader = iter(test_dataset)

        for i in range(len(test_dataloader.slides)):
            print(f'Starting Predictions: {datetime.datetime.now()}')
            for j in tqdm(range(test_dataloader.batches)):

                img_batch, coords = next(test_dataloader)
                pred_masks = model.predict(img_batch.to(device))

                # Assembling predicted masks into combined tif file
                test_dataloader.add_to_mask(pred_masks.detach().cpu().numpy(),coords)
            
            #final_mask = Image.fromarray(test_dataloader.combined_mask)
            #final_mask.save(output_dir+test_dataloader.current_slide.name+'.tif')
            test_dataloader.make_tiff(save_path = output_dir+test_dataloader.current_slide.name+'.tiff')

            #final_width,final_height = final_mask.size
            #scaled_final_mask = final_mask.resize((int(final_width/100),int(final_height/100)))
            #scaled_final_mask.save(output_dir+test_dataloader.current_slide.name+'_small.tif')
            
            try:
                test_dataloader = iter(test_dataloader)
            except StopIteration:
                print('Done!')
                break

        print(f'Done with Predictions: {datetime.datetime.now()}')