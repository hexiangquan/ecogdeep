import keras
from keras.preprocessing.ecog import EcogDataGenerator
from keras.preprocessing.image2 import ImageDataGenerator, center_crop
from keras.layers import Flatten, Dense, Input, Dropout, Activation, merge
from keras.layers.normalization import BatchNormalization
from keras.models import Model
from keras.layers import Convolution2D, MaxPooling2D
from hyperopt import Trials, fmin, tpe, hp, STATUS_OK
from keras.regularizers import l2
from itertools import izip
from convnetskeras.convnets import convnet
from ecogdeep.train.ecog_1d_model import ecog_1d_model
from ecogdeep.train.vid_alexnet_2towers_model import video_2tower_model

#from keras.imagenet_utils import decode_predictions, preprocess_input, _obtain_input_shape
import numpy as np
import pdb
import pickle
import glob

main_ecog_dir = '/home/wangnxr/dataset/ecog_vid_combined_a0f_day6/'
main_vid_dir = '/home/wangnxr/dataset/ecog_vid_combined_a0f_day6/'
#pre_shuffle_index = np.random.permutation(len(glob.glob('%s/train/*/*.npy' % main_ecog_dir)))
## Data generation ECoG
train_datagen_edf = EcogDataGenerator(
    start_time=3800,
    time_shift_range=200,
    gaussian_noise_range=0.001,
    center=False
)

test_datagen_edf = EcogDataGenerator(
    start_time=3800,
    center=True
)
channels = np.hstack([np.arange(36), np.arange(37, 68), np.arange(68, 92)])
dgdx_edf = train_datagen_edf.flow_from_directory(
    #'/mnt/cb46fd46_5_no_offset/train/',
    '%s/train/' % main_ecog_dir,
    batch_size=24,
    target_size=(1,len(channels),1000),
    final_size=(1,len(channels),1000),
    class_mode='binary',
    shuffle=False,
    channels = channels,
    pre_shuffle_ind=1)

dgdx_val_edf = test_datagen_edf.flow_from_directory(
    #'/mnt/cb46fd46_5_no_offset/test/',
    '%s/val/' % main_ecog_dir,
    batch_size=10,
    shuffle=False,
    target_size=(1,len(channels),1000),
    final_size=(1,len(channels),1000),
    channels = channels,
    class_mode='binary')

# Video data generators
train_datagen_vid = ImageDataGenerator(
    #rotation_range=40,
    rescale=1./255,
    #zoom_range=0.2,
    #horizontal_flip=True,
    random_crop=(227,227))

test_datagen_vid = ImageDataGenerator(
    rescale=1./255,
    center_crop=(227, 227))

#vid_model = video_2tower_model(weights="/home/wangnxr/vid_model_alexnet_2towers_dense1.h5")
#ecog_model = ecog_1d_model(weights="/home/wangnxr/model_ecog_1d_offset_15_1_3_1_3_v2.h5")
vid_model = video_2tower_model()
ecog_model = ecog_1d_model()

dgdx_vid = train_datagen_vid.flow_from_directory(
    '/%s/train/' % main_vid_dir,
    read_formats={'png'},
    target_size=(int(227), int(227)),
    resize_size = (int(340), int(256)),
    num_frames=11,
    batch_size=24,
    class_mode='binary',
    shuffle=False,
    pre_shuffle_ind=1)

dgdx_val_vid = test_datagen_vid.flow_from_directory(
    '/%s/val/' % main_vid_dir,
    read_formats={'png'},
    target_size=(int(227), int(227)),
    resize_size = (int(340), int(256)), 
    num_frames=11,
    batch_size=10,
    shuffle=False,
    class_mode='binary')
def izip_input(gen1, gen2):
    while 1:
        #pdb.set_trace()
        x1, y1 = gen1.next()
        x2 = gen2.next()[0]
        if not x1[0].shape[0] == x2.shape[0]:
            pdb.set_trace()
        x1.append(x2)
        yield x1, y1

train_generator = izip_input(dgdx_vid, dgdx_edf)
validation_generator = izip_input(dgdx_val_vid, dgdx_val_edf)

base_model_vid = Model(vid_model.input, vid_model.get_layer("fc2").output)
base_model_ecog = Model(ecog_model.input, ecog_model.get_layer("fc1").output)

frame_a = Input(shape=(3,227,227))
frame_b = Input(shape=(3,227,227))
ecog_series = Input(shape=(1,len(channels),1000))


tower1 = base_model_vid([frame_a, frame_b])
tower2 = base_model_ecog(ecog_series)
x = merge([tower1, tower2], mode='concat', concat_axis=-1)

x = Dropout(0.5)(x)
x = Dense(1024, W_regularizer=l2(0.01), name='merge1')(x)
x = BatchNormalization()(x)
x = Activation('relu')(x)
x = Dropout(0.5)(x)
x = Dense(256, W_regularizer=l2(0.01), name='merge2')(x)
x = BatchNormalization()(x)
x = Activation('relu')(x)
x = Dropout(0.5)(x)
x = Dense(1, name='predictions')(x)
#x = BatchNormalization()(x)
predictions = Activation('sigmoid')(x)

for layer in base_model_vid.layers:
    layer.trainable = False
for layer in base_model_ecog.layers:
    layer.trainable = False


model = Model(input=[frame_a, frame_b, ecog_series], output=predictions)
#model = Model(input=[base_model_vid.input, base_model_ecog.input], output=predictions)

sgd = keras.optimizers.SGD(lr=0.001, decay=1e-6, momentum=0.9)

model.compile(optimizer=sgd,
              loss='binary_crossentropy',
              metrics=['accuracy'])

history_callback = model.fit_generator(
    train_generator,
    samples_per_epoch=len(dgdx_vid.filenames),
    nb_epoch=40,
    validation_data=validation_generator,
    nb_val_samples=len(dgdx_val_vid.filenames))

model.save("/home/wangnxr/models/ecog_vid_model_alexnet_3towers_dense1_a0f.h5")
pickle.dump(history_callback.history, open("/home/wangnxr/models/ecog_vid_history_alexnet_3towers_dense1_a0f", "wb"))