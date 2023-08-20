import time
from threading import Thread
from queue import Queue
import serial

import numpy as np
import matplotlib.pyplot as plt

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import PySimpleGUI as sg
import matplotlib
matplotlib.use('TkAgg')

# confire correct relative paths to file
import sys, os
# sys.path.append(os.path.dirname(__file__))

GRBL_PORT = '/dev/ttyACM0'
GRBL_BUFFER_SIZE = 127
STATE_POLL_INTERVAL = 0.3


class GrblInterface:
    def __init__(self):
        self.new_report = False

        print(f"connecting to grbl at {GRBL_PORT}")
        self.ser = serial.serial_for_url(
            url=GRBL_PORT,
            baudrate=115200,
            timeout=20,
            write_timeout=0,
        )

        self.log = []

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
            self.log.append('>>  '+line)

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
                self.new_report = True
            else:
                print("<<<< " + out_temp)
                self.log.append('<<< '+out_temp)
        
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

        # plot work-area circles
        self.ax.add_artist(plt.Circle((0, 0), l1+l2, color='r', fill=False))
        self.ax.add_artist(plt.Circle((0, 0), l1-l2, color='r', fill=False))

        self.line, = self.ax.plot([], [], 'o-', lw=2)
        self.p1, = self.ax.plot([], [], 'ro', markersize=10)
        self.p2, = self.ax.plot([], [], 'bo', markersize=10)

        self.p_pos, = self.ax.plot([], [], 'g+', markersize=7) 
        self.trajectory = [[], []]
        self.traject_plot, = self.ax.plot([], [], 'g-', lw=1)

        self.plot_update(np.array([0, 0]))

    def plot_report(self, report):
        q = report['Qj'].split(',')
        q = np.array([float(q[0]), float(q[1])])
        q = q / 180 * np.pi
        xy = report['MPos'].split(',')
        xy = np.array([float(xy[0]), float(xy[1])])

        self.plot_update(q, xy)

    def plot_update(self, q, xy=None):
        x1 = self.l1*np.cos(q[0])
        y1 = self.l1*np.sin(q[0])
        x2 = x1 + self.l2*np.cos(q[1])
        y2 = y1 + self.l2*np.sin(q[1])

        self.line.set_data([0, x1, x2], [0, y1, y2])
        self.p1.set_data(x1, y1)
        self.p2.set_data(x2, y2)

        if xy is not None:
            self.trajectory[0].append(xy[0])
            self.trajectory[1].append(xy[1])
            self.traject_plot.set_data(self.trajectory[0], self.trajectory[1])
            self.p_pos.set_data(xy[0], xy[1])
                    
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()


def send_gcode(grbl, selected_file):
    with open(selected_file, 'r') as file:
        print(f"starting to stream {selected_file}")
        for line in file:
            line = line.strip()
            grbl.serial_send(line)
            #time.sleep(2)


def draw_figure(canvas, figure):
    tkcanvas = FigureCanvasTkAgg(figure, canvas)
    tkcanvas.draw()
    tkcanvas.get_tk_widget().pack(side='top', fill='both', expand=1)
    return tkcanvas



if __name__ == "__main__":
    l1 = 500
    l2 = 450
    plot = ScaraPlot(l1, l2)

    grbl = GrblInterface()

    # define the window layout
    terminal_layout = [
        [sg.Multiline(size=(70, 40), key='-ML-', autoscroll=True)],
        [sg.Input(key='-IN-', size=(60,1)), sg.Button('Send', bind_return_key=True)]
    ]
    view_layout = [
        [sg.Text('', size=(80,1), key='-MPOS-')],
        [sg.Text('', size=(80,1), key='-REPORT-')],
        [sg.Canvas(key='-CANVAS-')]
    ]

    layout = [[sg.Column(terminal_layout), sg.VSeperator(), sg.Column(view_layout)]]

    window = sg.Window('Simple Scara GRBL interface', layout, size=(1400, 700), finalize=True, element_justification='center', font='Helvetica 11')
    window.bind('<Up>', '_PREVIOUS_COMMAND_')
    window.bind('<Down>', '_NEXT_COMMAND_')

    # add the plot to the window
    tkcanvas = draw_figure(window['-CANVAS-'].TKCanvas, plot.fig)

    last_log_len = 0
    send_history = ['?']
    history_idx = 0
    while True:
        if grbl.new_report == True:
            grbl.new_report = False
            report = grbl.get_report()
            plot.plot_report(report)
            report_string_1 = f'State:{report.pop("State")}  MPos:{report.pop("MPos")}'
            report_string_2 = [f'{key}:{value} | ' for key, value in report.items()]
            window['-MPOS-'].update(report_string_1)
            window['-REPORT-'].update(''.join(report_string_2))
        if len(grbl.log) > last_log_len:
            last_log_len = len(grbl.log)
            window['-ML-'].update('\n'.join(grbl.log))

        event, values = window.read(timeout=500)
        print(event)
        if event == sg.WIN_CLOSED:
            break
        elif event == 'Send':
            msg = values['-IN-']
            print(f">>>> {msg}")
            grbl.serial_send(msg)
            if send_history[-1] != msg:
                send_history.append(msg)
                history_idx = len(send_history)-1
        elif event == '_PREVIOUS_COMMAND_':
            history_idx = max(0, history_idx-1)
            window['-IN-'].update(send_history[history_idx])
        elif event == '_NEXT_COMMAND_':
            history_idx = min(len(send_history)-1, history_idx+1)
            window['-IN-'].update(send_history[history_idx])


    grbl.close()
    window.close()
