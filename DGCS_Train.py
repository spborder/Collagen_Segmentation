# -*- coding: utf-8 -*-
"""
Created on Fri Jul 23 09:37:56 2021

@author: spborder


DGCS Training Loop 

from: https://github.com/qubvel/segmentation_models.pytorch/blob/master/examples/cars%20segmentation%20(camvid).ipynb

A lot of different segmentation networks are available from the 'segmentation_models_pytorch' module
"""

import torch
import numpy as np
import segmentation_models_pytorch as smp
from torch.utils.data import DataLoader

import matplotlib.pyplot as plt

import pandas as pd
from tqdm import tqdm
import sys


def back_to_reality(tar):
    
    # Getting target array into right format
    classes = np.shape(tar)[-1]
    dummy = np.zeros((np.shape(tar)[0],np.shape(tar)[1]))
    for value in range(classes):
        mask = np.where(tar[:,:,value]!=0)
        dummy[mask] = value

    return dummy

def apply_colormap(img):

    n_classes = np.shape(img)[-1]

    image = img[:,:,0]
    for cl in range(1,n_classes):
        image = np.concatenate((image, img[:,:,cl]),axis = 1)

    return image
    
def visualize(images,output_type):
    
    n = len(images)
    
    for i,key in enumerate(images):

        plt.subplot(1,n,i+1)
        plt.xticks([])
        plt.yticks([])
        plt.title(key)
        
        if len(np.shape(images[key]))==4:
            img = images[key][0,:,:,:]
        else:
            img = images[key]
            
        img = np.float32(np.moveaxis(img, source = 0, destination = -1))
        if key == 'Pred_Mask' or key == 'Ground_Truth':
            if output_type=='binary' or key == 'Ground_Truth':
                #print('using back_to_reality')
                img = back_to_reality(img)

                plt.imshow(img)
            if output_type == 'continuous' and not key == 'Ground_Truth':
                #print('applying colormap')
                img = apply_colormap(img)

                plt.imshow(img,cmap='jet')
        else:
            plt.imshow(img)

    return plt.gcf()

def visualize_continuous(images):

    n = len(images)
    for i,key in enumerate(images):

        plt.subplot(1,n,i+1)
        plt.xticks([])
        plt.yticks([])
        plt.title(key)

        if len(np.shape(images[key])) == 4:
            img = images[key][0,:,:,:]
        else:
            img = images[key]

        img = np.float32(np.moveaxis(img,source=0,destination=-1))
        if key == 'Pred_Mask' or key == 'Ground_Truth':
            img = apply_colormap(img)

            plt.imshow(img,cmap='jet')
        else:
            plt.imshow(img)

    return plt.gcf()
    
def Training_Loop(ann_classes, dataset_train, dataset_valid, model_dir, output_dir,target_type, nept_run):
    
    encoder = 'resnet34'
    encoder_weights = 'imagenet'

    if target_type=='binary':
        n_classes = len(ann_classes)
    elif target_type == 'nonbinary':
        n_classes = 1

    output_type = 'continuous'

    if target_type=='binary':
        active = 'softmax2d'
        loss = smp.losses.DiceLoss(mode='binary')

    elif target_type=='nonbinary':
        active = None
        loss = torch.nn.L1Loss()

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f'Is training on GPU available? : {torch.cuda.is_available()}')
    print(f'Device is : {device}')
    print(f'Torch Cuda version is : {torch.version.cuda}')    

    nept_run['encoder'] = encoder
    nept_run['encoder_pre_train'] = encoder_weights
    nept_run['Architecture'] = 'Unet++'
    nept_run['Loss'] = 'Dice'
    #nept_run['Metrics'] = 'IoU'
    nept_run['output_type'] = output_type
    
    model = smp.UnetPlusPlus(
            encoder_name = encoder,
            encoder_weights = encoder_weights,
            in_channels = 3,
            classes = n_classes,
            activation = active
            )
    
    # Sending model to current device ('cuda','cuda:0','cuda:1',or 'cpu')
    model = model.to(device)
    loss = loss.to(device)
    #print(f'Model: {model}')

    # Again only valid for smp version 0.1.0 or 0.2.0
    #metrics = [smp.metrics.IoU(threshold = 1/len(ann_classes))]
    
    optimizer = torch.optim.Adam([
            dict(params = model.parameters(), lr = 0.0001)
            ])

    #optimizer = optimizer.to(device)

    batch_size = 1
    train_loader = DataLoader(dataset_train, batch_size = batch_size, shuffle = True, num_workers = 12)
    valid_loader = DataLoader(dataset_valid, batch_size = batch_size, shuffle = True, num_workers = 4)
        
    # Initializing loss score
    train_loss = 0
    val_loss = 0
    
    # Maximum number of epochs defined here as well as how many steps between model saves and example outputs
    epoch_num = 120
    save_step = 10
    
    with tqdm(total = epoch_num, position = 0, leave = True, file = sys.stdout) as pbar:

        for i in range(0,epoch_num):
        
            # Turning on dropout
            model.train()

            # Controlling the progress bar, printing training and validation losses
            if i==1: 
                pbar.set_description(f'Epoch: {i}/{epoch_num}')
                pbar.update(i)
            elif i%5==0:
                pbar.set_description(f'Epoch: {i}/{epoch_num}, Train/Val Loss: {round(train_loss,4)},{round(val_loss,4)}')
                pbar.update(5)
        
            # Clear existing gradients in optimizer
            optimizer.zero_grad()

            # Loading training and validation samples from dataloaders
            train_imgs, train_masks = next(iter(train_loader))
            # Sending to device
            train_imgs = train_imgs.to(device)
            train_masks = train_masks.to(device)

            # Testing whether the images were actually sent to cuda
            #print(f'Images: {train_imgs}')
            #print(f'Images are on device: {train_imgs.get_device()}')

            # Running predictions on training batch
            train_preds = model(train_imgs)
            print(f'Prediction shape: {train_preds.shape}')
            print(f'GT mask shape: {train_masks.shape}')
            # Calculating loss
            train_loss = loss(train_preds,train_masks)

            # Backpropagation
            train_loss.backward()
            train_loss = train_loss.item()
            nept_run['training_loss'].log(train_loss)

            # Updating optimizer
            optimizer.step()
            #print(f'Model device: {next(model.parameters()).device}')

            # Validation (don't want it to influence gradients in network)
            with torch.no_grad():
                # This turns off any dropout in the network 
                model.eval()

                val_imgs, val_masks = next(iter(valid_loader))
                val_imgs = val_imgs.to(device)
                val_masks = val_masks.to(device)

                val_preds = model(val_imgs)
                val_loss = loss(val_preds,val_masks)
                val_loss = val_loss.item()
                nept_run['validation_loss'].log(val_loss)

            # Saving model if current i is a multiple of "save_step"
            # Also generating example output segmentation and uploading that to Neptune
            if i%save_step == 0:
                torch.save(model.state_dict(),model_dir+f'Collagen_Seg_Model_{i}.pth')

                if batch_size==1:
                    current_img = val_imgs.cpu().numpy()
                    current_gt = val_masks.cpu().numpy()
                    current_pred = val_preds.cpu().numpy()
                else:
                    current_img = val_imgs[0].cpu().numpy()
                    current_gt = val_masks[0].cpu().numpy()
                    current_pred = val_preds[0].cpu().numpy()

                if target_type=='binary':
                    current_pred = current_pred.round()

                img_dict = {'Image':current_img, 'Pred_Mask':current_pred,'Ground_Truth':current_gt}

                if target_type=='binary':
                    fig = visualize(img_dict,output_type)
                elif target_type=='nonbinary':
                    fig = visualize_continuous(img_dict)


                fig.savefig(output_dir+f'Training_Epoch_{i}_Example.png')
                nept_run[f'Example_Output_{i}'].upload(output_dir+f'Training_Epoch_{i}_Example.png')

    if not i%save_step==0:
        torch.save(model.state_dict(),model_dir+f'Collagen_Seg_Model_{i}.pth')

    return model_dir+f'Collagen_Seg_Model_{i}.pth'



