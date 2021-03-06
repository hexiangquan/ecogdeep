import keras
from keras.preprocessing.ecog import EcogDataGenerator
from keras.preprocessing.image2 import ImageDataGenerator, center_crop
from keras.layers import Flatten, Dense, Input, Dropout, Activation, merge, TimeDistributed
from keras.layers.normalization import BatchNormalization
from keras.layers.recurrent import LSTM
from keras.models import Model
from hyperopt import Trials, fmin, tpe, hp, STATUS_OK
from keras.regularizers import l2
from itertools import izip
from keras.callbacks import ModelCheckpoint
from ecogdeep.train.ecog_1d_model_seq import ecog_1d_model
from ecogdeep.train.vid_model_seq import vid_model

#from keras.imagenet_utils import decode_predictions, preprocess_input, _obtain_input_shape
import numpy as np
import pdb
import pickle
import glob

main_ecog_dir = '/home/wangnxr/dataset/ecog_vid_combined_a0f_day6/'
main_vid_dir = '/home/wangnxr/dataset/ecog_vid_combined_a0f_day6/'


# Video data generators
train_datagen_vid = ImageDataGenerator(
    #rotation_range=40,
    rescale=1./255,
    #zoom_range=0.2,
    #horizontal_flip=True,
    random_crop=(224,224),
    keep_frames=range(6,9))

test_datagen_vid = ImageDataGenerator(
    rescale=1./255,
    center_crop=(224, 224),
    keep_frames=range(6,9))

#vid_model = video_2tower_model(weights="/home/wangnxr/vid_model_alexnet_2towers_dense1.h5")
#ecog_model = ecog_1d_model(weights="/home/wangnxr/model_ecog_1d_offset_15_1_3_1_3_v2.h5")
vid_model = vid_model()

dgdx_vid = train_datagen_vid.flow_from_directory(
    '/%s/train/' % main_vid_dir,
    img_mode="seq",
    read_formats={'png'},
    target_size=(int(224), int(224)),
    num_frames=11,
    batch_size=24,
    class_mode='binary',
    shuffle=False,
    pre_shuffle_ind=1)

dgdx_val_vid = test_datagen_vid.flow_from_directory(
    '/%s/test/' % main_vid_dir,
    img_mode="seq",
    read_formats={'png'},
    target_size=(int(224), int(224)),
    num_frames=11,
    batch_size=10,
    shuffle=False,
    class_mode='binary')

def izip_input(gen1, gen2):
    while 1:
        #pdb.set_trace()
        x1, y1 = gen1.next()
        x2 = gen2.next()[0]
        if not x1.shape[0] == x2.shape[0]:
            pdb.set_trace()
        yield [x1, x2], y1

train_generator = dgdx_vid
validation_generator = dgdx_val_vid
base_model_vid = Model(vid_model.input, vid_model.get_layer("fc1").output)

frame_a = Input(shape=(3,3,224,224))


x = base_model_vid(frame_a)
x = Dropout(0.5)(x)
x = TimeDistributed(Dense(256, W_regularizer=l2(0.01), name='merge2'))(x)
x = BatchNormalization()(x)
x = Activation('relu')(x)
x = Dropout(0.5)(x)
x = LSTM(20, dropout_W=0.2, dropout_U=0.2, name='lstm')(x)
x = Dense(1, name='predictions')(x)
#x = BatchNormalization()(x)
predictions = Activation('sigmoid')(x)

for layer in base_model_vid.layers:
    layer.trainable = True

model = Model(input=frame_a, output=predictions)
#model = Model(input=[base_model_vid.input, base_model_ecog.input], output=predictions)

sgd = keras.optimizers.SGD(lr=0.001, decay=1e-6, momentum=0.9)

model_savepath = "/home/wangnxr/models/vid_model_lstm_a0f_3st_pred"
model.compile(optimizer=sgd,
              loss='binary_crossentropy',
              metrics=['accuracy'])
checkpoint = ModelCheckpoint("%s_chkpt.h5" % model_savepath, monitor='val_acc', verbose=1, save_best_only=True, mode='max')
history_callback = model.fit_generator(
    train_generator,
    samples_per_epoch=len(dgdx_vid.filenames),
    nb_epoch=40,
    validation_data=validation_generator,
    nb_val_samples=len(dgdx_val_vid.filenames), callbacks=[checkpoint])

model.save("%s.h5" % model_savepath)
pickle.dump(history_callback.history, open("/home/wangnxr/history/vid_history_lstm_a0f_3st_pred", "wb"))
