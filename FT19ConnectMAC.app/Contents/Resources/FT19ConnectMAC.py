import sys
import socket
import os
from PyQt5.QtGui import (QIcon)
from pynput.keyboard import Key, Controller, Listener
from PyQt5.QtWidgets import (QWidget,
                         QPushButton, QApplication, QGridLayout, QSystemTrayIcon, QMenu, QAction)
from PyQt5.QtCore import QThread, QObject, pyqtSignal, pyqtSlot

TCPKeyTrackerIP = ""
shiftPressed = 0
ServerState = ""

class Worker(QObject):

    finished = pyqtSignal()  # give worker class a finished signal
    sig_done = pyqtSignal(int)
    sig_ServerClientState = pyqtSignal(int)
    

    def __init__(self, parent=None):
        self.__id = id
        QObject.__init__(self, parent=parent)
        self.continue_run = True  # provide a bool run condition for the class,
        self.serverClientState = "State: not connected" 

    def do_work(self):
        global TCPKeyTrackerIP
        global ServerState
        ServerState = "Init"
        ServerTypState = "UDPServer"

        while self.continue_run:  # give the loop a stoppable condition
            if ServerTypState == "UDPServer":
                if ServerState == "Init":
                    self.serverClientState = "State: not connected"
                    self.sig_ServerClientState.emit(self.__id)
                    ServerClientState = "not connected"
                    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
                    client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    client.bind(("", 5555))
                    ServerState = "WaitForClient"
                    print("UDP_Init")

                if ServerState == "WaitForClient":
                    data, addr = client.recvfrom(1024)
                    data = data.decode("utf-8")
                    if data[:10] == "ServerName":
                        TCPKeyTrackerIP = data[10:]
                        print(TCPKeyTrackerIP)
                        client.connect(addr)
                        client.send(b'LSControl')
                        client.close()
                        ServerState = "Init"
                        ServerTypState = "TCPServer"
                    print("UDP_Waiting")

            if ServerTypState == "TCPServer":
                if ServerState == "Init":
                    ipAddress = socket.gethostbyname_ex(socket.gethostname())[-1][0]
                    serversocket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                    serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    serversocket.bind((ipAddress,5555))
                    serversocket.listen(5)
                    ServerState = "ReceivingData"
                    print("TCP_Init")

                if ServerState == "ReceivingData":
                    self.serverClientState = "State: connected"
                    self.sig_ServerClientState.emit(self.__id)
                    connection, address = serversocket.accept()
                    print("Send something")
                    buf = connection.recv(64)
                    buf = buf.decode("utf-8")
                    if len(buf) > 0:
                        if buf == "Exit":
                            serversocket.close()
                            ServerState = "Init"
                            ServerTypState = "UDPServer"
                        elif buf == "UserAction":
                            connection.send(b'dsf')

                        else:
                            self.sig_done.emit(self.__id)
                            self.keystroke = buf 
                    print("TCP_Receiving") 



    def stop(self):
        self.continue_run = False  # set the run condition to false on stop

class YourThreadName(QThread):

    def __init__(self):
        QThread.__init__(self)

    def __del__(self):
        self.wait()

    def on_press(self, key):
        #print('{0} release'.format(key))
        global shiftPressed
        if (key == Key.shift_l):
            shiftPressed = 1
            print(shiftPressed)


    def on_release(self, key):
        global TCPKeyTrackerIP
        global shiftPressed   
        global ServerState  
        clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #ipAddress = socket.gethostbyname(socket.gethostname())
        with clientsocket as s:
            if (ServerState == "ReceivingData"):
                if (key == Key.shift_l):
                    shiftPressed = 0
                    print(shiftPressed)
                if (TCPKeyTrackerIP != ""):    
                    print(str(key))
                    if(key == Key.tab and shiftPressed == 1):
                        s.connect((TCPKeyTrackerIP, 5554))    
                        print("ShiftTab")
                        s.sendall(b"ShiftTab")  
                    if(key == Key.tab and shiftPressed == 0):
                        s.connect((TCPKeyTrackerIP, 5554))
                        print("Tab")
                        s.sendall(b"Tab")
                    if(key != Key.tab):
                        s.connect((TCPKeyTrackerIP, 5554))
                        s.sendall(bytes(str(key), 'utf-8'))
                    
                                         



    def run(self):
        with Listener(
            on_press=self.on_press,
            on_release=self.on_release) as listener:
                listener.join()

class Gui(QWidget):

    stop_signal = pyqtSignal()  # make a stop signal to communicate with the worker in another thread

    def __init__(self):
        super(Gui, self).__init__()
        self.initUI()
        self.keyboard = Controller()

    def initUI(self):

        def close_app():
            sys.exit()

        # Create the icon
        self.icon = QIcon("AppIcon256.icns")
        self.ServerClientState = "State: not connected"

        # Create the tray
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self.icon)
        self.tray.setVisible(True)

        # Create the menu
        self.menu = QMenu()
        self.closeServer = QAction("Close Server")
        self.closeServer.triggered.connect(close_app)
        self.connectedLabel = QAction(self.ServerClientState)
        self.menu.addAction(self.connectedLabel)
        self.menu.addAction(self.closeServer)



        # Add the menu to the tray
        self.tray.setContextMenu(self.menu)

        # Thread:
        self.thread = QThread()
        self.worker = Worker()
        self.stop_signal.connect(self.worker.stop)  # connect stop signal to worker stop method
        self.worker.moveToThread(self.thread)

        self.worker.finished.connect(self.thread.quit)  # connect the workers finished signal to stop thread
        self.worker.finished.connect(self.worker.deleteLater)  # connect the workers finished signal to clean up worker
        self.thread.finished.connect(self.thread.deleteLater)  # connect threads finished signal to clean up thread

        self.thread.started.connect(self.worker.do_work)
        self.thread.finished.connect(self.worker.stop)
        self.worker.sig_done.connect(self.on_worker_done)
        self.worker.sig_ServerClientState.connect(self.sig_ServerClientStateChange)

    @pyqtSlot(int)
    def on_worker_done(self, worker_id):
        self.press_button(self.worker.keystroke)     

    @pyqtSlot(int)
    def sig_ServerClientStateChange(self, worker_id):
        self.connectedLabel = QAction(self.worker.serverClientState)
        self.menu.addAction(self.connectedLabel)
        self.menu.addAction(self.closeServer)
    
    def press_button(self, input):
        print(input)
        singleInputs = [x.strip() for x in input.split(';')]
        print(singleInputs)
        indexOfSingleInputs = 0
        for inputs in singleInputs:
            if singleInputs[indexOfSingleInputs] == "UMSCHALT LINKS":
                if singleInputs[indexOfSingleInputs+1] == "STRG LINKS":
                    with self.keyboard.pressed(Key.shift_l):
                        with self.keyboard.pressed(Key.ctrl):
                            self.keyboard.press(singleInputs[indexOfSingleInputs+2])
                            self.keyboard.release(singleInputs[indexOfSingleInputs+2])
                            print("Umschalt Links")
                            print(singleInputs[indexOfSingleInputs+2]) 
                            indexOfSingleInputs = indexOfSingleInputs+2 

                else:
                    with self.keyboard.pressed(Key.shift_l):
                        self.keyboard.press(singleInputs[indexOfSingleInputs+1])
                        self.keyboard.release(singleInputs[indexOfSingleInputs+1])     
                        print("Umschalt Links")
                        print(singleInputs[indexOfSingleInputs+1]) 
                        indexOfSingleInputs = indexOfSingleInputs+1               
            elif singleInputs[indexOfSingleInputs] == "STRG LINKS":
                with self.keyboard.pressed(Key.ctrl):
                    self.keyboard.press(singleInputs[indexOfSingleInputs+1])
                    self.keyboard.release(singleInputs[indexOfSingleInputs+1]) 
                    print("STRG")
                    print(singleInputs[indexOfSingleInputs+1]) 
                    indexOfSingleInputs = indexOfSingleInputs+1 
            elif singleInputs[indexOfSingleInputs] == "ENTER":
                    self.keyboard.press(Key.enter)
                    self.keyboard.release(Key.enter)    
            elif singleInputs[indexOfSingleInputs] == "f1":
                    self.keyboard.press(Key.f1)
                    self.keyboard.release(Key.f1)  
            elif singleInputs[indexOfSingleInputs] == "f2":
                    self.keyboard.press(Key.f2)
                    self.keyboard.release(Key.f2)  
            elif singleInputs[indexOfSingleInputs] == "f3":
                    self.keyboard.press(Key.f3)
                    self.keyboard.release(Key.f3)
            elif singleInputs[indexOfSingleInputs] == "f4":
                    self.keyboard.press(Key.f4)
                    self.keyboard.release(Key.f4)
            elif singleInputs[indexOfSingleInputs] == "f5":
                    self.keyboard.press(Key.f5)
                    self.keyboard.release(Key.f5)
            elif singleInputs[indexOfSingleInputs] == "f6":
                    self.keyboard.press(Key.f6)
                    self.keyboard.release(Key.f6)
            elif singleInputs[indexOfSingleInputs] == "f7":
                    self.keyboard.press(Key.f7)
                    self.keyboard.release(Key.f7)
            elif singleInputs[indexOfSingleInputs] == "f8":
                    self.keyboard.press(Key.f8)
                    self.keyboard.release(Key.f8)
            elif singleInputs[indexOfSingleInputs] == "f9":
                    self.keyboard.press(Key.f9)
                    self.keyboard.release(Key.f9)       
            elif singleInputs[indexOfSingleInputs] == "f10":
                    self.keyboard.press(Key.f10)
                    self.keyboard.release(Key.f10)  
            elif singleInputs[indexOfSingleInputs] == "f11":
                    self.keyboard.press(Key.f11)
                    self.keyboard.release(Key.f11)    
            elif singleInputs[indexOfSingleInputs] == "f12":
                    self.keyboard.press(Key.f12)
                    self.keyboard.release(Key.f12)  
            elif singleInputs[indexOfSingleInputs] == "LEFT":
                    self.keyboard.press(Key.left)
                    self.keyboard.release(Key.left)  
            elif singleInputs[indexOfSingleInputs] == "RIGHT":
                    self.keyboard.press(Key.right)
                    self.keyboard.release(Key.right)  
            elif singleInputs[indexOfSingleInputs] == "UP":
                    self.keyboard.press(Key.up)
                    self.keyboard.release(Key.up)  
            elif singleInputs[indexOfSingleInputs] == "DOWN":
                    self.keyboard.press(Key.down)
                    self.keyboard.release(Key.down)      
            elif singleInputs[indexOfSingleInputs] == "POS1":
                    self.keyboard.press(Key.home)
                    self.keyboard.release(Key.home)             
            else:
                self.keyboard.press(singleInputs[indexOfSingleInputs])
                self.keyboard.release(singleInputs[indexOfSingleInputs]) 
                print(singleInputs[indexOfSingleInputs])            

            indexOfSingleInputs = indexOfSingleInputs+1
            if indexOfSingleInputs == len(singleInputs):
                break
        #self.keyboard.press(input)
        #self.keyboard.release(input) 

if __name__ == '__main__':  
    app = QApplication(sys.argv)
    myThread = YourThreadName()
    myThread.start()
    gui = Gui()
    gui.thread.start()
    sys.exit(app.exec_())   

     