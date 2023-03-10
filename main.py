# -*- coding: utf-8 -*-
from keras.models import Sequential, Model
from keras.layers import Flatten, Dropout, Activation, Permute
from keras.layers import Convolution2D, MaxPooling2D
from keras import backend as K
K.set_image_data_format( 'channels_last' )

import numpy as np
import cv2
from scipy.spatial.distance import cosine as dcos
from scipy.io import loadmat

import os
from multiprocessing.dummy import Pool
#Bonus :
from threading import * 

import serial
arduino = serial.Serial(port='COM5', baudrate=115200 , timeout=.1)

### Trouver les visages et les découper
##################################################
def auto_crop_image(image):
    if image is not None:
        im = image.copy()
        # Importation de l' HaarCascade
        faceCascade = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")
        
        # Lecture de l'image
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Détection des visages sur l'image
        faces = faceCascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        faces = faceCascade.detectMultiScale(gray, 1.2, 5)
        
        if len(faces) > 0:
            # Draw a rectangle around the faces
            for (x, y, w, h) in faces:
                cv2.rectangle(image, (x, y), (x+w, y+h), (0, 255, 0), 2)        
            (x, y, w, h) = faces[0]
            center_x = x+w/2
            center_y = y+h/2
            height, width, channels = im.shape
            b_dim = min(max(w,h)*1.2,width, height)
            box = [center_x-b_dim/2, center_y-b_dim/2, center_x+b_dim/2, center_y+b_dim/2]
            box = [int(x) for x in box]
            # Crop Image
            if box[0] >= 0 and box[1] >= 0 and box[2] <= width and box[3] <= height:
                crpim = im[box[1]:box[3],box[0]:box[2]]
                crpim = cv2.resize(crpim, (224,224), interpolation = cv2.INTER_AREA)
                print("Found {0} faces!".format(len(faces)))
                return crpim, image, (x, y, w, h)
    return None, image, (0,0,0,0)

### Step 3 : Création du model CNN pour le réseau de neuronnes
#################################################################
def convblock(cdim, nb, bits=3):
    L = []
    for k in range(1,bits+1):
        convname = 'conv'+str(nb)+'_'+str(k)
        L.append( Convolution2D(cdim, kernel_size=(3, 3), padding='same', activation='relu', name=convname) )
    L.append( MaxPooling2D((2, 2), strides=(2, 2)) )
    return L

def vgg_face_blank():
    withDO = True #
    if True:
        mdl = Sequential()
        mdl.add( Permute((1,2,3), input_shape=(224,224,3)) )
        for l in convblock(64, 1, bits=2):
            mdl.add(l)
        for l in convblock(128, 2, bits=2):
            mdl.add(l)        
        for l in convblock(256, 3, bits=3):
            mdl.add(l)            
        for l in convblock(512, 4, bits=3):
            mdl.add(l)            
        for l in convblock(512, 5, bits=3):
            mdl.add(l)        
        mdl.add( Convolution2D(4096, kernel_size=(7, 7), activation='relu', name='fc6') )
        if withDO:
            mdl.add( Dropout(0.5) )
        mdl.add( Convolution2D(4096, kernel_size=(1, 1), activation='relu', name='fc7') )
        if withDO:
            mdl.add( Dropout(0.5) )
        mdl.add( Convolution2D(2622, kernel_size=(1, 1), activation='relu', name='fc8') )
        mdl.add( Flatten() )
        mdl.add( Activation('softmax') )
        
        return mdl
    
    else:
        raise ValueError('not implemented')
        
def copy_mat_to_keras(kmodel):
    kerasnames = [lr.name for lr in kmodel.layers]
    prmt = (0,1,2,3)

    for i in range(l.shape[1]):
        matname = l[0,i][0,0].name[0]
        if matname in kerasnames:
            kindex = kerasnames.index(matname)
            l_weights = l[0,i][0,0].weights[0,0]
            l_bias = l[0,i][0,0].weights[0,1]
            f_l_weights = l_weights.transpose(prmt)
            assert (f_l_weights.shape == kmodel.layers[kindex].get_weights()[0].shape)
            assert (l_bias.shape[1] == 1)
            assert (l_bias[:,0].shape == kmodel.layers[kindex].get_weights()[1].shape)
            assert (len(kmodel.layers[kindex].get_weights()) == 2)
            kmodel.layers[kindex].set_weights([f_l_weights, l_bias[:,0]])

### Step 4 : Création des vecteurs les plus proches avec les img dans la bdd
############################################
def generate_database(folder_img = "images"):
    database = {}
    for the_file in os.listdir(folder_img):
        file_path = os.path.join(folder_img, the_file)
        try:
            if os.path.isfile(file_path):
               name = the_file.split(".")[0]
               img = cv2.imread(file_path)
               crpim, srcimg, (x, y, w, h) = auto_crop_image(img)
               vector_image = crpim[None,...]
               database[name] = featuremodel.predict(vector_image)[0,:]
        except Exception as e:
            print(e)
    return database

def find_closest(img, database, min_detection=2.5):
    imarr1 = np.asarray(img)
    imarr1 = imarr1[None,...]
    #Prediction
    fvec1 = featuremodel.predict(imarr1)[0,:]
    #Personne la plus ressemblante dans la bdd
    dmin = 0.0
    umin = ""
    for key, value in database.items():
        fvec2 = value
        dcos_1_2 = dcos(fvec1, fvec2)
        if umin == "":
            dmin = dcos_1_2
            umin = key
        elif dcos_1_2 < dmin:
            dmin = dcos_1_2
            umin = key
    if dmin > min_detection:
        umin = ""
    return umin, dmin

### Main function
#################
def webcam_face_recognizer(database):
    cv2.namedWindow("preview")
    vc = cv2.VideoCapture(0)
    ready_to_detect_identity = True
    name = ""
    
    while vc.isOpened():
        _, frame = vc.read()
        img = frame
        imgcrop,img, (x, y, w, h) = auto_crop_image(img)
        
        if ready_to_detect_identity and imgcrop is not None:
            ready_to_detect_identity = False
            pool = Pool(processes=1)
            name, ready_to_detect_identity = pool.apply_async(recognize_image, [imgcrop, database]).get()
            if name :
                print("Bonsoir")
                arduino.write(bytes('1','utf-8'))
            pool.close()
            cv2.putText(img = frame, text = name, org = (int(x),int(y+h+20)), fontFace = cv2.FONT_HERSHEY_SIMPLEX, thickness= 2, fontScale = 1, color = (0, 255, 0))
        key = cv2.waitKey(100)
        cv2.imshow("preview", img)

        if key == 27: #Arrêt du programme
            break
    cv2.destroyWindow("preview")
    
### Reconnaissance Faciale prenom
###################
def recognize_image(img, database):
    print("******** PROCEDING FACIAL RECOGNITION ********")
    name, dmin = find_closest(img ,database)      
    print("******** RESUME ANALYSIS ********")
    return name, True


### Initialisation de la reconnaissance faciale
###############################
# Appel de la fonction du model CNN (Neuronnes)
facemodel = vgg_face_blank()
# Appel de l'IA près entrainé
data = loadmat('vgg-face.mat', matlab_compatible=False, struct_as_record=False)
l = data['layers']
description = data['meta'][0,0].classes[0,0].description

copy_mat_to_keras(facemodel)
# Appel de la fonction Model qui va permettre de determiner si le visage est dans la bdd
featuremodel = Model( inputs = facemodel.layers[0].input, outputs = facemodel.layers[-2].output )

### Utilisation de la reconnaisance faciale
####################################
db = generate_database()

# Analyse de toutes les images
webcam_face_recognizer(db)

 