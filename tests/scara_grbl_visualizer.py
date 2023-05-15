import time
from threading import Thread
from queue import Queue
import serial

import numpy as np
import matplotlib.pyplot as plt

# confire correct relative paths to file
import sys, os
# sys.path.append(os.path.dirname(__file__))

GRBL_PORT = '/dev/ttyACM0'
GRBL_BUFFER_SIZE = 127
STATE_POLL_INTERVAL = 0.1


class GrblInterface:
    def __init__(self):
        print(f"connecting to grbl at {GRBL_PORT}")
        self.ser = serial.serial_for_url(
            url=GRBL_PORT,
            baudrate=115200,
            timeout=20,
            write_timeout=0,
        )

        self._quit = False
        self.report = ''
        self.chars_in_buffer = Queue()
        self.lines_to_send = Queue()

        self.thread_receiver = Thread(target=self._receiver, daemon=True)
        self.thread_receiver.start()
        self.thread_sender = Thread(target=self._sender, daemon=True)
        self.thread_sender.start()
        self.thread_poll = Thread(target=self.poll_report, daemon=True)
        self.thread_poll.start()

        time.sleep(0.5)
        for msg in ('$X','$I'):
            self.serial_send(msg)

    def serial_send(self, line):
        if line in ('!', '?', '~'):
            # realtime commands are send directly
            self.ser.write(line.encode('ascii'))
        else:
            self.lines_to_send.put(line)

    def _sender(self):
        print("start sending thread")
        while not self._quit:
            line = self.lines_to_send.get()
            print(">> " + line)

            # wait until there is space in the buffer
            buf_size = 127
            while (sum(self.chars_in_buffer.queue)+len(line) >= GRBL_BUFFER_SIZE-2):
                time.sleep(0.001)

            self.ser.write((line + '\n').encode('ascii'))
            self.chars_in_buffer.put(len(line)+1)
        
        print("exiting sender thread")

    def _receiver(self):
        # Continuously receives and does the corresponding actions.
        print("start receiving thread")
        while not self._quit:
            out_temp = self.ser.readline()
            out_temp = out_temp.decode('ascii').strip()
            if not out_temp:
                continue

            if 'ok' in out_temp: 
                # grbl handled a line
                print("<ok< "+out_temp)
                self.chars_in_buffer.get()                
            elif out_temp[0] == '<' and out_temp[-1] == '>':
                self.report = out_temp
                print("<??< " + out_temp)
            else:
                print("<<<< " + out_temp)
        
        print("exiting receiver thread")

    def poll_report(self):
        print(f"start polling for reports, every {STATE_POLL_INTERVAL} seconds")
        while not self._quit:
            self.serial_send('?')
            time.sleep(STATE_POLL_INTERVAL)
        
        print("exiting poll thread")

    def get_report(self):
        items = self.report[1:-1].split('|')
        report = {}
        report['State'] = items.pop(0)
        for item in items:
            key, value = item.split(':')
            report[key] = value
        return report
    
    def close(self):
        self._quit = True
        self.thread_receiver.join()
        self.thread_sender.join()
        self.thread_poll.join()
        self.ser.close()


# visualize scara robot in an animated matplotlib plot 
class ScaraPlot:
    def __init__(self, l1, l2):
        self.l1 = l1
        self.l2 = l2

        r = (l1 + l2) * 1.1
        self.fig, self.ax = plt.subplots()
        self.ax.set_xlim(-r, r)
        self.ax.set_ylim(-r, r)
        self.ax.set_aspect('equal')
        self.ax.grid(True)
        self.ax.set_xlabel('X (m)')
        self.ax.set_ylabel('Y (m)')
        self.ax.set_title('SCARA Robot')
        plt.ion()
        plt.show(block=False)

        self.line, = self.ax.plot([], [], 'o-', lw=2)
        self.p1, = self.ax.plot([], [], 'ro', markersize=10)
        self.p2, = self.ax.plot([], [], 'bo', markersize=10)

        self.plot(np.array([0, 0]))

    def plot(self, q):
        x1 = self.l1*np.cos(q[0])
        y1 = self.l1*np.sin(q[0])
        x2 = x1 + self.l2*np.cos(q[1])
        y2 = y1 + self.l2*np.sin(q[1])

        # print(f"q=({q[0]:.0f},{q[1]:.0f}) p1=({x1:.2f},{y1:.2f}) p2=({x2:.2f},{y2:.2f})")

        self.line.set_data([0, x1, x2], [0, y1, y2])
        self.p1.set_data(x1, y1)
        self.p2.set_data(x2, y2)
        
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()


update_plot = True
def plot_update(grbl, plot):
    while update_plot:
        report = grbl.get_report()

        q = report['Qj'].split(',')
        q = np.array([float(q[0]), float(q[1])])
        plot.plot(q)
        time.sleep(0.05)

def send_gcode(grbl, selected_file):
    with open(selected_file, 'r') as file:
        print(f"starting to stream {selected_file}")
        for line in file:
            line = line.strip()
            grbl.serial_send(line)
            time.sleep(2)

# animate a simple trajectory
if __name__ == "__main__":
    l1 = 700
    l2 = 600
    plot = ScaraPlot(l1, l2)

    # t = np.linspace(0, 3, 100)
    # q = np.zeros((2, t.size))
    # q[0,:] = 2*t
    # q[1,:] = 1.5*t

    # input("Press enter to animate")
    # for qi in q.T:
    #     sp.plot(qi)
    #     time.sleep(0.1)


    grbl = GrblInterface()
    time.sleep(2)

    # t_plot = Thread(target=plot_update, args=(grbl, plot))
    # t_plot.start()

    # stream gcode file
    selected_file = os.path.join(os.path.dirname(__file__), 'test.gcode')
    # selected_file = 'dog tag (g-code).gc'
    t_gcode = Thread(target=send_gcode, args=(grbl, selected_file))
    t_gcode.start()

    plot_update(grbl, plot)

    t_gcode.join()
    
    while len(grbl.chars_in_buffer.queue) > 0:
        time.sleep(0.1)

    grbl.close()
    print("done")


# test command: $X G1 X200 Y200 F1000
