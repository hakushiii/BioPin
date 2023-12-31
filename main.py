# IMPORTS
import serial
import numpy as np
import json
import torch
import collections
import time

import eeg as eg

from random import randint

# MODEL
class ProfessorXModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.conv_block_1 = torch.nn.Sequential(
            torch.nn.Conv1d(in_channels=1, out_channels=16, kernel_size=3),
            torch.nn.ReLU(),
            torch.nn.Conv1d(in_channels=16, out_channels=16, kernel_size=2),
            torch.nn.ReLU(),
        )
        self.conv_block_2 = torch.nn.Sequential(
            torch.nn.Conv1d(in_channels=16, out_channels=16, kernel_size=2),
            torch.nn.ReLU(),
            torch.nn.MaxPool1d(kernel_size=2),
        )
        self.conv_block_3 = torch.nn.Sequential(
            torch.nn.Conv1d(in_channels=16, out_channels=16, kernel_size=2),
            torch.nn.ReLU(),
            torch.nn.MaxPool1d(kernel_size=2),
        )
        self.classifier = torch.nn.Sequential(
            torch.nn.Flatten(),
            torch.nn.Linear(in_features=16*11, out_features=128),
            torch.nn.Linear(in_features=128, out_features=1),
            torch.nn.Sigmoid()
        )

    def forward(self, x):
        snr = 1.
        std = torch.std(x)
        x += (2. * torch.rand(x.shape) - 1.) * 2. * std * snr

        result = self.classifier(self.conv_block_3(self.conv_block_2(self.conv_block_1(x))))
        return torch.squeeze(result)


# LOAD TRAINED MODEL
model = torch.load('Model/model_overall.pt')

# EVALUATE MODEL
model.eval()

# COMMANDS
def commandFunction(eog, eeg):

    length = 50
    queue = collections.deque(maxlen=length)
    count,timer = 0, 0
    checker = 0
    tresh_attention = 70
    command = 0
    
    while (eog and eeg) != None:
        val = eog.readline()
        try:
            output = val.decode('UTF-8').rstrip()
            output = float(output)
            output = output * 50
        except ValueError:
            output = 0.00

        queue.append(output)

        if count < 50:
            count += 1
        else:
            queue_numpy = np.array(queue).astype(float)
            queue_tensor = torch.from_numpy(queue_numpy[:]).unsqueeze(0).unsqueeze(0).to(torch.float32)

            with torch.inference_mode():
                result = model(queue_tensor)

            while checker == 0:

                if eeg.attention >= tresh_attention:
                    direction = 'Forward'
                    checker = 1
                    command = 1
                elif eeg.meditation >= tresh_attention:
                    direction = 'Reverse'
                    checker = 1
                    command = 4
                elif result.item() >= 0.7:
                    direction = 'Rightward'
                    checker = 1
                    command = 3
                elif result.item() <= 0.3:
                    direction = 'Leftward'
                    checker = 1
                    command = 2
                else:
                    direction = 'Stop'
                    checker = 1
                    command = 0

            while checker == 1:
                timer+=1

                if timer >= 3000:
                    checker = 0
                    timer = 0
                    command = 0
                
                return queue, result, command, direction

if __name__ == '__main__':

    is_connected = 1

    while True:

        to_json = {
                'is_connected': is_connected
        }
        json_object = json.dumps(to_json)

        with open('UI/bt.json', 'w') as f:
            f.write(json_object)
            f.close()

        eog = serial.Serial('/dev/rfcomm0', 9600)
        eeg = eg.Headwear('/dev/rfcomm1')
        mtr = serial.Serial('/dev/ttyACM0', 9600)
        is_connected = 1
        print('Devices Connected')

        if is_connected == 0:
            pass
            #try:
            #    eog = serial.Serial('/dev/rfcomm0', 9600)
            #    eeg = eg.Headwear('/dev/rfcomm1')
            #    mtr = serial.Serial('/dev/ttyACM0', 9600)
            #    print('Devices Connected')
            #    is_connected = 1
            #    time.sleep(1)
            #
            #except:
            #    is_connected = 0
            #    print('Devices not Connected')
            #    time.sleep(1)

        if is_connected == 1:
            count = 0
            try:
                queue, result, command , direction = commandFunction(eog, eeg)

                if command == 2 or 3:
                    stay_command = True
                    refresh = command
                    command = 0
                if stay_command == True and count <= 4:
                    if eeg.attention > 55:
                        command = refresh
                    else:
                        command = 0
                    count += 1
                elif stay_command == True and count > 4:
                    command = 0
                    stay_command = False
                    count = 0

                f = open('UI/data.json')
                data = json.load(f)
                speed = data['combinedValues']
                f.close()

                speed = int(speed)

                command_new = str(command) + ':' + str(speed)

                to_json = {
                    'eog': queue[0]
                }
                json_object = json.dumps(to_json)

                with open('UI/eog.json', 'w') as f:
                    f.write(json_object)
                    f.close()

                to_json = {
                    'direction': direction
                }
                json_object = json.dumps(to_json)

                with open('UI/direction.json', 'w') as f:
                    f.write(json_object)
                    f.close()

                print('EOG:', f'{result.item():.2f} | ', f'ATTENTION: {eeg.attention:2d} |', f'MEDITATION: {eeg.meditation:2d} |', f'Signal: {eeg.poor_signal} |',f'COMMANND: {command_new}', f'|| {direction}')

                if command != 0:
                    try:
                        mtr.write(str(command_new).encode('utf-8'))
                    except KeyboardInterrupt:
                        mtr.write('0:0'.encode('utf-8'))
            
            except:
                print('Dead')
