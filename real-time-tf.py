import time
from pylsl import StreamInlet, resolve_byprop
import matplotlib.pyplot as plt
import numpy as np
from scipy.fft import fft, ifft

srate = 256
class MuseLsl():
    def __init__(self):
        self.inlet = None
        self.retry_attempts = 5
        self.retry_delay = 2  # seconds

    def connect(self):
        for i in range(self.retry_attempts):
            try:
                streams = resolve_byprop('type', 'EEG', timeout=2)
                if len(streams) > 0:
                    self.inlet = StreamInlet(streams[0])
                    print('Successfully connected to EEG stream.')
                    return
                else:
                    print(f'Attempt {i+1} failed. Could not find EEG stream. Retrying in {self.retry_delay} seconds.')
                    time.sleep(self.retry_delay)
            except Exception as e:
                print(f'Attempt {i+1} failed with error: {e}. Retrying in {self.retry_delay} seconds.')
                time.sleep(self.retry_delay)
        
        raise RuntimeError('Failed to connect to EEG stream after multiple attempts.')

    def disconnect(self):
        if self.inlet is not None:
            self.inlet.close_stream()
            print('Disconnected from EEG stream.')

    def read_data(self):
        if self.inlet is None:
            raise RuntimeError('Must be connected to EEG stream to read data.')
        
        try:
            time_to_wait = 0.5 # in seconds
            temp_data = []
            counter = 0

            nData = round(srate*time_to_wait)
            cmwX, nKern, frex = get_cmwX(nData)
            while True:
               
                sample, timestamp = self.inlet.pull_sample()
                
                if counter != nData:
                    temp_data.append(sample)
                    counter += 1
                else:
                    process_new_data(np.array(temp_data)[:,:4].T, cmwX, nKern, frex)
                    temp_data = []
                    counter = 0

        except KeyboardInterrupt:
            print('Stopping data collection.')
        finally:
            self.disconnect()


# create a figure
fig = plt.figure()
ax = fig.add_subplot(111)
plt.ion()
fig.show()
fig.canvas.draw()

def process_new_data(new_data, cmwX, nKern, frex):
    times = np.linspace(0,1, new_data.shape[1]) # lets just keep it constant for now, TODO: make real time later

    # Perform the time-frequency analysis on new_data
    # This could be your `time_frequency` function, but modified to return
    # the time-frequency representation rather than plotting it
    tf_data = time_frequency(new_data, cmwX, nKern)
    
    # Clear the current plot
    ax.clear()
    
    # Update the plot with the new time-frequency representation
    ax.contourf(times, frex, tf_data, 40, cmap='jet') 
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Frequencies (Hz)')
    ax.set_title('Real-Time Power Spectrum')
    
    # Redraw the figure
    fig.canvas.draw()
    plt.pause(0.01)  # pause a bit so that plots are updated


def get_cmwX(nData, freqrange=[1,45], numfrex=43):
    '''
        returns cmwX of shape frequency x nConv
    '''
    wavtime = np.arange(-2,2-1/srate,1/srate)
    nKern = len(wavtime)
    nConv = nData + nKern - 1
    frex = np.linspace(freqrange[0],freqrange[1],numfrex)
   # create complex morlet wavelets array
    cmwX = np.zeros((numfrex, nConv), dtype=complex)
    for fi in range(numfrex):
        pi = np.pi

         # number of cycles
        numcyc = np.linspace(3,15,numfrex);

        # create time-domain wavelet
        s = numcyc[fi] / (2*pi*frex[fi])
        twoSsquared = (2*s) ** 2
        cmw = np.exp(2*1j*pi*frex[fi]*wavtime) * np.exp( (-wavtime**2) / twoSsquared )


        # compute fourier coefficients of wavelet and normalize
        cmwX[fi, :] = fft(cmw, nConv)
        cmwX[fi, :] = cmwX[fi, :] / max(cmwX[fi, :])

    return cmwX, nKern, frex

def time_frequency(data, cmwX, nKern, channel_labels=None):
    '''
        creates a time frequency power plot of the data and plots it for
        every channel
        
        data -> of shape channels x time
        times -> the times array for the given data
        freqrange -> extract only these frequencies (in Hz)
        numfrex -> number of frequencies between lowest and highest

        returns average time frequency plot and frequency range
    '''
    
    assert data.shape[0] < data.shape[1], "data shape incorrect"
    assert channel_labels is None or len(channel_labels) == data.shape[0], "channel_labels must be of same length as number of channels"

    # set up convolution parameters
    nData   = data.shape[1]
    nConv   = nData + nKern - 1
    halfwav = (nKern-1)//2

    # initialize time-frequency output matrix
    tf = np.zeros((data.shape[0], cmwX.shape[0], data.shape[1])) # channels X frequency X times

    # loop over channels
    for chani in range(data.shape[0]):

        # compute Fourier coefficients of EEG data (doesn't change over frequency!)
        eegX = fft(data[chani, :] , nConv)

        # perform convolution and extract power (vectorized across frequencies)
        as_ = ifft(cmwX * eegX[None, :], axis=1)
        as_ = as_[:, halfwav: -halfwav]
        tf[chani, :, :] = np.abs(as_) ** 2
        
    tf = np.mean(tf, axis=0)

    return tf


if __name__ == "__main__":
    muse_lsl = MuseLsl()
    try:
        muse_lsl.connect()
        muse_lsl.read_data()
    except Exception as e:
        print(f'An error occurred: {e}')
    finally:
        muse_lsl.disconnect()