import numpy
import pyvisa as visa
import time
import math
import sys
import matplotlib

matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from matplotlib.figure import Figure

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6 import uic

# wczytanie listy dostępnych urządzeń
rm = visa.ResourceManager()
devices = rm.list_resources()  # pobranie listy dostępnych urządzeń


# pobranie danych niezbędnych do utworzenia przebiegu przy wybraniu pobierania danych w sposób binarny
def get_numerical_values(oscyloskop):
    # Dane używane podczas tworzenia wektora czasu (potrzebne do wyrysowania przebiegu)
    XINC = oscyloskop.query_ascii_values(
        ":WAVeform:XINCrement?")  # wartość przeskalowania w pozycji X (okres pomiędzy każdą próbką)
    XREF = oscyloskop.query_ascii_values(
        ":WAVeform:XREFerence?")  # zwraca pierwszy punkt na ekranie lub w pamięci wewnętrznej)
    # Dane potrzebne do poprawnej konwersji liczb na volty
    YOR = oscyloskop.query_ascii_values(":WAVeform:YORigin?")  # wartość przesunięcia pionowego w kierunku Y
    YREF = oscyloskop.query_ascii_values(
        ":WAVeform:YREFerence?")  # zwracana jest wartość zależna od bieżącego trybu odczytu danych
    YINC = oscyloskop.query_ascii_values(":WAVeform:YINCrement?")  # zwraca nam wartość przeskalowania w pozycji Y

    return XINC, XREF, YOR, YREF, YINC

# dane potrzebne do odczytania pełnego spektrum
def get_memory_depth(oscyloskop):
    samp_time = oscyloskop.query_ascii_values(":ACQuire:SRATe?")  # zwraca aktualny czas próbkowania
    time_base = oscyloskop.query_ascii_values("TIMebase:SCALe?")  # pobranie podstawy czasu
    DepthMemory = (time_base[0] * 12) * samp_time[0]  # obliczenie MemoryDepth
    return DepthMemory


# ustawienie początku i końca pobierania danych
def data_download_limit(oscyloskop, start=1, stop=500000):
    oscyloskop.write(f":WAVeform:STARt {str(start)}")  # ustawienie początku pobierania danych
    oscyloskop.write(f":WAVeform:STOP {str(stop)}")  # ustawienie końca pobierania danych


# algorytm pozwalajacy na uzyskanie całego spectrum
def get_all_data(oscyloskop, DepthMemory, sample=500000):
    dane = oscyloskop.query_binary_values(":WAVeform:DATA?", datatype='B')  # pobranie danych z oscyloskopu

    if DepthMemory > sample:
        licznik = 1  # ustawienie wartości licznika na 1
        liczba_petli = math.ceil(
            DepthMemory / sample)  # zaokrąglenie w górę liczby pętli potrzebnych do pobrania całego spektrum

        while licznik < liczba_petli:  # wykonywanie pobierania danych do momentu zrównania się licznika z liczbą pętli

            beginning = (licznik * sample) + 1      # obliczenie początku pobierania danych zależnego od aktualnego obiegu pętli
            if licznik == liczba_petli -1:          # warunek pozwalający na pobranie wszystkich danych
                end = DepthMemory                   # ustalenie memorydepth na koniec pobierania próbek
            else:
                end = (licznik + 1) * sample  # obliczenie końca pobierania danych zależnego od aktualnego obiegu pętli

            data_download_limit(oscyloskop, beginning, end)
            dane.extend(oscyloskop.query_binary_values(":WAVeform:DATA?",
                                                       datatype='B'))  # rozszerzenie danych o kolejne informacje
            licznik += 1  # zwiększenie licznika

    return dane


# zatrzymanie pracy oscyloskopu
def stop():
    oscyloskop.write(":STOP")


# wznowienie pracy oscyloskopu
def start():
    oscyloskop.write(":RUN")


# konwersja odczytanych danych na przebieg napięcia
def make_volt(dane, XINC, XREF, YOR, YREF, YINC):
    volt = (numpy.asarray(dane) - YOR[0] - YREF[0]) * YINC[0]  # przeliczenie danych na wartości napięcia

    return volt, XINC, XREF, YREF, YINC


# funkcja pozwalająca na pobranie aktualnie wyświetlanego przebiegu z jednego kanału w celu poźniejszego wyrysowania
def program(oscyloskop):
    stop()  # wywołanie funkcji zatrzymującą pracę oscylokskopu
    time.sleep(0.5)  # wstrzymanie obiegu pętli na 0.5s w celu uniknięcia błędów w pobieraniu danych
    XINC, XREF, YOR, YREF, YINC = get_numerical_values(
        oscyloskop)  # wywołanie funkcji pobierającej dane niezbędne do wyrysowania przebiegu
    DepthMemory = get_memory_depth(oscyloskop)  # wywołanie funkcji pobierającej dane do uzyskania pełnego spektrum
    data_download_limit(oscyloskop)  # wywołanie funkcji ustawiajacej początek i koniec pobierania danych od 1 do 250000
    dane = get_all_data(oscyloskop, DepthMemory)  # pobranie pełnego spektrum
    start()  # wywołanie funkcji startującej pracę oscyloskopu
    frq = oscyloskop.query_ascii_values(":MEAS:ITEM? FREQ")  # pobranie aktualnej częstotliwości obserwowanego sygnału
    data, XINC, XREF, YREF, YINC = make_volt(dane, XINC, XREF, YOR, YREF,
                                             YINC)  # wywołanie funkcji konwertującej dane na wartości napięcia

    return data, XINC, XREF, frq


# funkcja pozwalająca na pobranie aktualnie wyświetlanego przebiegu z dwóch kanałów w celu poźniejszego wyrysowania
def programTwoChannel(oscyloskop):
    time.sleep(0.5)
    stop()
    oscyloskop.write(":WAVeform:SOURce CHANnel1")
    oscyloskop.write(":MEASure:SOURce CHANnel1")
    frqTwoChannel1 = oscyloskop.query_ascii_values(":MEAS:ITEM? FREQ")

    XINCTwoChannel1, XREFTwoChannel1, YORTwoChannel1, YREFTwoChannel1, YINCTwoChannel1 = get_numerical_values(
        oscyloskop)
    DepthMemory = get_memory_depth(oscyloskop)
    data_download_limit(oscyloskop)
    daneTwoChannel1 = get_all_data(oscyloskop, DepthMemory)
    start()
    dataTwoChannel1, XINCTwoChannel1, XREFTwoChannel1, YREFTwoChannel1, YINCTwoChannel1 = make_volt(daneTwoChannel1,
                                                                                                    XINCTwoChannel1,
                                                                                                    XREFTwoChannel1,
                                                                                                    YORTwoChannel1,
                                                                                                    YREFTwoChannel1,
                                                                                                    YINCTwoChannel1)

    stop()
    time.sleep(0.5)
    oscyloskop.write(":WAVeform:SOURce CHANnel2")
    oscyloskop.write(":MEASure:SOURce CHANnel2")
    frqTwoChannel2 = oscyloskop.query_ascii_values(":MEAS:ITEM? FREQ")

    XINCTwoChannel2, XREFTwoChannel2, YORTwoChannel2, YREFTwoChannel2, YINCTwoChannel2 = get_numerical_values(
        oscyloskop)
    DepthMemory = get_memory_depth(oscyloskop)
    data_download_limit(oscyloskop)
    daneTwoChannel2 = get_all_data(oscyloskop, DepthMemory)
    start()
    dataTwoChannel2, XINCTwoChannel2, XREFTwoChannel2, YREFTwoChannel2, YINCTwoChannel2 = make_volt(daneTwoChannel2,
                                                                                                    XINCTwoChannel2,
                                                                                                    XREFTwoChannel2,
                                                                                                    YORTwoChannel2,
                                                                                                    YREFTwoChannel2,
                                                                                                    YINCTwoChannel2)

    return dataTwoChannel1, dataTwoChannel2, XINCTwoChannel1, XINCTwoChannel2, XREFTwoChannel1, XREFTwoChannel2, frqTwoChannel1, frqTwoChannel2


# funkcja pozwalająca na obliczenie wartości maksymalnej, minimalnej oraz skutecznej przebiegu  dla jednego kanału
def measure(data):
    maxValue = max(data)  # obliczenie wartości maksymalnej
    minValue = min(data)  # obliczenie wartości minimalnej
    rms = numpy.sqrt(numpy.mean(data ** 2))  # obliczenie wartości skutecznej

    return maxValue, minValue, rms


# funkcja pozwalająca na obliczenie wartości maksymalnej, minimalnej, skutecznej oraz pomiarów mocy przebiegów dla dwóch kanałów
def measureTwoChannel(data1, data2):
    Ui = 0  #
    P = 0  # wyzerowanie zmiennych
    S = 0  #
    Q = 0  #

    maxValueCh1 = max(data1)  # obliczenie wartości maksymalnej
    minValueCh1 = min(data1)  # obliczenie wartości minimalnej
    rmsCh1 = numpy.sqrt(numpy.mean(data1 ** 2))  # obliczenie wartości skutecznej

    maxValueCh2 = max(data2)  # obliczenie wartości maksymalnej
    minValueCh2 = min(data2)  # obliczenie wartości minimalnej
    rmsCh2 = numpy.sqrt(numpy.mean(data2 ** 2))  # obliczenie wartości skutecznej

    if len(data1) == len(data2):                # sprawdzenie czy wektory są równej długośći w celu uniknięcia błędów
        for i in range(len(data1)):             # obliczenie sumy iloczynów napięcia i prądu
            Ui += data1[i] * data2[i]

        S = rmsCh1 * rmsCh2                     # obliczenie mocy pozornej
        P = Ui / len(data1)                     # obliczenie mocy czynnej
        Q = numpy.sqrt(S ** 2 - P ** 2)         # obliczenie mocy biernej
    else:
        S = 9.9e+37                             #przypisanie wartości w momencie nierównej długości wektorów
        P = 9.9e+37
        Q = 9.9e+37

    return maxValueCh1, minValueCh1, rmsCh1, maxValueCh2, minValueCh2, rmsCh2, P, S, Q


# stworzenie klasy MplCanvas służącej do rysowania przebiegów
class MplCanvas(FigureCanvas):

    def __init__(self, parent=None, width=5, height=4):
        fig = Figure(figsize=(width, height))
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)
        fig.tight_layout()


# stworzenie klasy QMainWindow w celu utworzenia aplikacji
class Oscilloscope(QtWidgets.QMainWindow):

    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        self.comboBoxMeasure = None  #
        self.comboBoxCanals = None  # predefinicja widgetów comboBox
        self.ListOfDevices = None  #

        self.pushButtonStopMeasure = None  # predefinicja widgetów pushButton
        self.pushButtonMeasure = None  #

        self.ui = uic.loadUi('gui.ui', self)  # wczytanie stworzonego gui

        # stworzenie połączenia pomiędzy widgetami a funkcjami programu
        self.doubleSpinBoxMax.valueChanged.connect(self.GetMaxValue)
        self.radioButtonOn.clicked.connect(self.RadioButtonOnClicked)
        self.radioButtonOff.clicked.connect(self.RadioButtonOffClicked)
        self.pushButtonMeasure.clicked.connect(self.StartWorker)
        self.pushButtonStopMeasure.clicked.connect(self.StopWorker)

        # dodanie możliwości zapisu danych
        self.actionSave.triggered.connect(self.SaveFile)

        # przypisanie akcji actionExit metody quit()
        self.actionExit.triggered.connect(QtCore.QCoreApplication.instance().quit)

        self.resize(988, 900)  # ustalenia rozmiarów okna
        self.setWindowIcon(QtGui.QIcon('agh.jpg'))  # ustawienie ikony aplikacji

        # odwołanie do innych stworzonych klas
        self.ThreadClass = ThreadClass()
        self.ThreadClassTwoCh = ThreadClassTwoChannel()

        # dodanie do Widgetu ComboBox(ListOfDevices) dostępnych urządzeń
        self.ListOfDevices.addItems(devices)
        self.ListOfDevices.setPlaceholderText("--Wybierz Urządzenie--")
        self.ListOfDevices.setCurrentIndex(-1)
        self.ListOfDevices.currentIndexChanged.connect(self.Connection)

        # dodanie do Widgetu comboBoxCanals wybranych kanałów
        self.comboBoxCanals.addItem("Channel 1")
        self.comboBoxCanals.addItem("Channel 2")
        self.comboBoxCanals.addItem("Channel 1 | Channel 2")
        self.comboBoxCanals.setPlaceholderText("--Wybierz Kanał--")
        self.comboBoxCanals.setCurrentIndex(-1)
        self.comboBoxCanals.currentIndexChanged.connect(self.ChannelChoice)


        # dodanie do Widgetu ComboBoxMeasure dostępnych trybów pomiaru
        self.comboBoxMeasure.addItem("Pojedynczy")
        self.comboBoxMeasure.addItem("Ciągły")
        self.comboBoxMeasure.setPlaceholderText("--Wybierz Tryb--")
        self.comboBoxMeasure.setCurrentIndex(-1)
        self.comboBoxMeasure.currentIndexChanged.connect(self.MeasureMode)

        # dodanie do Mainwindow miejsca na wykres oraz dodanie toolbara
        self.canvas = MplCanvas(self, width=5, height=4)
        toolbar = NavigationToolbar2QT(self.canvas, self)
        self.ui.gridLayout_6.addWidget(toolbar)
        self.ui.gridLayout_6.addWidget(self.canvas)

        # początkowe ukrycie elementów odpowiedzialnych za wyświetlanie wyników pomiarów
        self.widget2CH.hide()
        self.widgetCH.hide()

        # przypisanie wartości początkowej poszczególnym zmiennym
        self.DeviceNumber = -1
        self.ChannelNumber = -1
        self.Mode = -1
        self.isChacked = False
        self.ThreadClass.isOnChacked(self.isChacked)

    # funkcja odpowiedzialna za zapis danych do pliku txt
    def SaveFile(self):
        try:
            name = QtWidgets.QFileDialog.getSaveFileName(self, "Save File", " ", "All Files(*);;Text Files(*.txt)")
            file = open(name[0], 'w')

            if self.ChannelNumber == 0 or self.ChannelNumber == 1:
                time = czas
                data = datasend

                file.write(f"CH{self.ChannelNumber + 1} [V],Czas [S]\n")
                for i, x in enumerate(data):
                    file.write(f'{x},{time[i]}\n')
                file.close()

            elif self.ChannelNumber == 2:
                time1 = czas1
                data1 = dataToSave1
                data2 = dataToSave2

                file.write("CH1 [V],CH2 [V],Czas [S]\n")
                for i, x in enumerate(data1):
                    file.write(f'{x},{data2[i]},{time1[i]}\n')
                file.close()

            else:
                file.close()

        except:
            msg = QtWidgets.QMessageBox()
            msg.setWindowTitle("Błąd!")
            msg.setText("Poprawnie wybierz nazwe pliku\nlub najpierw dokonaj pomiaru!")
            msg.exec()

    # funkcja odpowiedzalna za przesłanie aktualnie wybranej wartości napięcia wyzwolania do klas ThreadClass i ThreadClassTwoCh
    def GetMaxValue(self, value):
        self.ThreadClass.getMaxValue(value)
        self.ThreadClassTwoCh.getMaxValue(value)

    # funkcja odpowiedzalna za przesłanie aktualnie wybranego trybu pomiaru do klas ThreadClass i ThreadClassTwoCh
    def MeasureMode(self, value):
        self.ThreadClass.getMode(value)
        self.ThreadClassTwoCh.getMode(value)
        self.Mode = value

    # funkcja odpowiedzalna za przesłanie aktualnie flagi do klas ThreadClass i ThreadClassTwoCh
    def RadioButtonOnClicked(self):
        self.isOnChacked = True
        self.ThreadClass.isOnChacked(self.isOnChacked)
        self.ThreadClassTwoCh.isOnChacked(self.isOnChacked)

    # funkcja odpowiedzalna za przesłanie aktualnie flagi do klas ThreadClass i ThreadClassTwoCh
    def RadioButtonOffClicked(self):
        self.isOnChacked = False
        self.ThreadClass.isOnChacked(self.isOnChacked)
        self.ThreadClassTwoCh.isOnChacked(self.isOnChacked)

    # funkcja odpowiedzialna za wybranie urządzenia z listy urządzeń i ustawienie jako domyślny
    def Connection(self, value):
        global oscyloskop
        self.DeviceNumber = value
        try:
            oscyloskop = rm.open_resource(self.ListOfDevices.currentText())
            oscyloskop.write(":WAVeform:MODE RAW")
            oscyloskop.write(":WAVeform:FORMat BYTE")
            sprawdzenie = oscyloskop.query_ascii_values(":WAVeform:XINCrement?")
        except:
            msg = QtWidgets.QMessageBox()
            msg.setWindowTitle("Błąd!")
            msg.setText("Wybrane urządzenie nie jest wspierane!")
            msg.exec()
            self.ListOfDevices.setPlaceholderText("--Wybierz Urządzenie--")
            self.ListOfDevices.setCurrentIndex(-1)

    # funkcja odpowiedzialna za wybór aktualnego kanału, wywoływana w wybrania kanału
    def ChannelChoice(self, value):
        self.ChannelNumber = value
        if value == 0 or value == 1:
            try:
                oscyloskop.write(f":WAVeform:SOURce CHANnel{value + 1}")
                oscyloskop.write(f":MEASure:SOURce CHANnel{value + 1}")
            except:
                msg = QtWidgets.QMessageBox()
                msg.setWindowTitle("Błąd!")
                msg.setText("Najpierw wybierz urządzenie!")
                msg.exec()
                self.comboBoxCanals.setPlaceholderText("--Wybierz Kanał--")
                self.comboBoxCanals.setCurrentIndex(-1)
        else:
            try:
                oscyloskop.write(f":WAVeform:SOURce CHANnel{1}")
            except:
                msg = QtWidgets.QMessageBox()
                msg.setWindowTitle("Błąd!")
                msg.setText("Wybrane najpierw wybierz urządzenie!")
                msg.exec()
                self.comboBoxCanals.setPlaceholderText("--Wybierz Kanał--")
                self.comboBoxCanals.setCurrentIndex(-1)

    # funkcja odpowiedzialna za uruchomienie procedury odczytywania danych oraz za wywołanie wielowątkowości
    def StartWorker(self):
        if self.DeviceNumber == -1 or self.ChannelNumber == -1 or self.Mode == -1:
            msg = QtWidgets.QMessageBox()
            msg.setWindowTitle("Błąd!")

            if self.DeviceNumber == -1 and self.ChannelNumber == -1 and self.Mode == -1:
                msg.setText("Poprawnie skonfiguruj program!")
                msg.exec()
                return
            elif self.DeviceNumber == -1 and self.ChannelNumber == -1:
                msg.setText("Wybierz poprawnie urządzenie\noraz kanał!")
                msg.exec()
                return

            elif self.DeviceNumber == -1:
                msg.setText("Wybierz poprawnie urządzenie!")
                msg.exec()
                return

            elif self.Mode == -1:
                msg.setText("Wybierz tryb pracy!")
                msg.exec()
                return
            else:
                msg.setText("Wybierz poprawnie kanał!")
                msg.exec()
                return

        else:
            if self.Mode == 1:
                self.pushButtonMeasure.setEnabled(False)
                self.comboBoxCanals.setEnabled(False)
                self.ListOfDevices.setEnabled(False)
                self.comboBoxMeasure.setEnabled(False)
                self.doubleSpinBoxMax.setEnabled(False)
                self.radioButtonOn.setEnabled(False)
                self.radioButtonOff.setEnabled(False)

            if self.ChannelNumber == 0 or self.ChannelNumber == 1:

                self.widgetCH.show()
                self.widget2CH.hide()
                self.thread = ThreadClass(parent=None)
                self.thread.start()
                self.thread.signal.connect(self.Measure)

            elif self.ChannelNumber == 2:

                self.widgetCH.hide()
                self.widget2CH.show()
                self.threadTwo = ThreadClassTwoChannel(parent=None)
                self.threadTwo.start()
                self.threadTwo.signalTwoChannel.connect(self.MeasureTwoChannel)

    # funkcja odpowiedzialna za zatrzymanie procedury odczytywania danych oraz za przerwanie wielowątkowości
    def StopWorker(self):
        if self.ChannelNumber == 0 or self.ChannelNumber == 1:
            self.thread.stop()

        elif self.ChannelNumber == 2:
            self.threadTwo.stop()

        self.comboBoxCanals.setEnabled(True)
        self.ListOfDevices.setEnabled(True)
        self.pushButtonMeasure.setEnabled(True)
        self.comboBoxMeasure.setEnabled(True)
        self.doubleSpinBoxMax.setEnabled(True)
        self.radioButtonOn.setEnabled(True)
        self.radioButtonOff.setEnabled(True)

# funkcja odpowiedzialna za rysowanie przebiegów oraz wyświetlenie wyników pomiarów z wczesniej pobranych danych dla pomiarów w przypadku jednego kanału
    def Measure(self, data, XINC, XREF, frq, max, min, rms):
        global czas
        global datasend

        datasend = data

        czas = numpy.linspace(XREF * 4, XINC * 4 * len(data), len(data))
        avgValue = numpy.mean(data)

        self.canvas.axes.clear()
        self.canvas.axes.plot(czas, data, label=f"CH{self.ChannelNumber + 1}")
        self.canvas.axes.set_xlim(xmin=czas[0], xmax=czas[-1])
        self.canvas.axes.yaxis.grid(True, linestyle='--')
        self.canvas.axes.xaxis.grid(True, linestyle='--')
        self.canvas.axes.set_title(f"CH{self.ChannelNumber + 1}")
        self.canvas.axes.set_ylabel("V")
        self.canvas.axes.set_xlabel(f"Czas [S]")
        self.canvas.axes.legend(loc='upper right')
        self.canvas.draw()

        self.lineEditMax.setText(str(round(max, 3)) + " V")
        self.lineEditMin.setText(str(round(min, 3)) + " V")
        self.lineEditRms.setText(str(round(rms, 3)) + " V")
        self.lineEditAmp.setText(str(round(avgValue, 3)) + " V")

        if frq == 9.9e+37:
            self.lineEditFreq.setText("******** Hz")
        else:
            self.lineEditFreq.setText(str(round(frq, 1)) + " Hz")

    # funkcja odpowiedzialna za rysowanie przebiegów oraz wyświetlenie wyników pomiarów z wczesniej pobranych danych dla pomiarów w przypadku dwóch kanałów
    def MeasureTwoChannel(self, data1, data2, XINC1, XINC2, XREF1, XREF2, max1, min1, rms1, max2, min2, rms2, frq1,
                          frq2, P, S, Q):
        global czas1
        global czas2
        global dataToSave1
        global dataToSave2

        dataToSave1 = data1
        dataToSave2 = data2

        czas1 = numpy.linspace(XREF1 * 4, XINC1 * 4 * len(data1), len(data1))
        czas2 = numpy.linspace(XREF2 * 4, XINC2 * 4 * len(data2), len(data2))
        avgValue1 = numpy.mean(data1)
        avgValue2 = numpy.mean(data2)

        self.canvas.axes.clear()
        self.canvas.axes.plot(czas1, data1, label="CH1")
        self.canvas.axes.plot(czas2, data2, label="CH2")
        self.canvas.axes.set_xlim(xmin=czas1[0], xmax=czas1[-1])
        self.canvas.axes.yaxis.grid(True, linestyle='--')
        self.canvas.axes.xaxis.grid(True, linestyle='--')
        self.canvas.axes.set_title(f"CH1 i CH2")
        self.canvas.axes.set_ylabel("V")
        self.canvas.axes.set_xlabel(f"Czas [S]")
        self.canvas.axes.legend(loc='upper right')
        self.canvas.draw()

        self.lineEditCH1Max.setText(str(round(max1, 3)) + " V")
        self.lineEditCH1Min.setText(str(round(min1, 3)) + " V")
        self.lineEditCH1Rms.setText(str(round(rms1, 3)) + " V")
        self.lineEditCH1Amp.setText(str(round(avgValue1, 3)) + " V")

        if frq1 == 9.9e+37:
            self.lineEditCH1Frq.setText("******** Hz")
        else:
            self.lineEditCH1Frq.setText(str(round(frq1, 1)) + " Hz")

        self.lineEditCH2Max.setText(str(round(max2, 3)) + " V")
        self.lineEditCH2Min.setText(str(round(min2, 3)) + " V")
        self.lineEditCH2Rms.setText(str(round(rms2, 3)) + " V")
        self.lineEditCH2Amp.setText(str(round(avgValue2, 3)) + " V")

        if frq2 == 9.9e+37:
            self.lineEditCH2Frq.setText("******** Hz")
        else:
            self.lineEditCH2Frq.setText(str(round(frq2, 1)) + " Hz")

        if P == 9.9e+37 or S == 9.9e+37 or Q == 9.9e+37:
            self.lineEditPActive.setText("******** W")
            self.lineEditPApparent.setText("******** VA")
            self.lineEditPReactive.setText("******** Var")
        else:
            self.lineEditPActive.setText(str(round(P, 3)) + " W")
            self.lineEditPApparent.setText(str(round(S, 3)) + " VA")
            self.lineEditPReactive.setText(str(round(Q, 3)) + " Var")




# stworzenie klasy QThread obsługującą wielowątkowość aplikacji dla jednego kanału
class ThreadClass(QtCore.QThread):
    signal = QtCore.pyqtSignal(list, float, float, float, float, float, float)

    def __init__(self, parent=None):
        super(ThreadClass, self).__init__(parent)
        self.isRunning = True

    # funkcja wywoływana w momencie startu porcedury wielowątkowości dla jednego kanału
    def run(self):

        while True:
            data, XINC, XREF, frq = program(oscyloskop)

            x = numpy.array(data)
            x = numpy.delete(x, numpy.arange(0, x.size, 2))
            x1 = numpy.array(x)
            x1 = numpy.delete(x1, numpy.arange(0, x1.size, 2))
            max, min, rms = measure(x1)
            if self.isRunning:
                self.signal.emit(x1, XINC[0], XREF[0], frq[0], max, min, rms)
            else:
                break

            if isChecked:
                if max >= MaxValue:
                    break

            if Mode == 0:
                break

    # funkcja wywoływana w momencie zatrzymania porcedury wielowątkowości
    def stop(self):
        self.isRunning = False

    # funkcja pobierająca aktualnie wybrany tryb pracy
    def getMode(self, value):
        global Mode
        Mode = value

    # funkcja pobierająca aktualną wartość wyzwalania
    def getMaxValue(self, value):
        global MaxValue
        MaxValue = value

    # funkcja pobierająca aktualny stan widgetów RadioButtonOn/Off
    def isOnChacked(self, OnChecked):
        global isChecked
        isChecked = OnChecked


# funkcja wywoływana w momencie startu porcedury wielowątkowości dla dwóch kanałów
class ThreadClassTwoChannel(QtCore.QThread):
    signalTwoChannel = QtCore.pyqtSignal(list, list, float, float, float, float, float, float, float, float,
                                               float, float, float, float, float, float, float)

    def __init__(self, parent=None):
        super(ThreadClassTwoChannel, self).__init__(parent)
        self.isRunning = True

    # funkcja wywoływana w momencie startu porcedury wielowątkowości dla dwóch kanałów
    def run(self):

        while True:
            daneTwoChannel1, daneTwoChannel2, XINCTwoChannel1, XINCTwoChannel2, XREFTwoChannel1, XREFTwoChannel2, frqTwoChannel1, frqTwoChannel2 = programTwoChannel(
                oscyloskop)

            xTwoChannel1 = numpy.array(daneTwoChannel1)
            xTwoChannel1 = numpy.delete(xTwoChannel1, numpy.arange(0, xTwoChannel1.size, 2))
            xTwoChannel12 = numpy.array(xTwoChannel1)
            xTwoChannel12 = numpy.delete(xTwoChannel12, numpy.arange(0, xTwoChannel12.size, 2))

            xTwoChannel2 = numpy.array(daneTwoChannel2)
            xTwoChannel2 = numpy.delete(xTwoChannel2, numpy.arange(0, xTwoChannel2.size, 2))
            xTwoChannel22 = numpy.array(xTwoChannel2)
            xTwoChannel22 = numpy.delete(xTwoChannel22, numpy.arange(0, xTwoChannel22.size, 2))

            maxTwoChannel1, minTwoChannel1, rmsTwoChannel1, maxTwoChannel2, minTwoChannel2, rmsTwoChannel2, P, S, Q = measureTwoChannel(
                xTwoChannel12, xTwoChannel22)

            if self.isRunning:
                self.signalTwoChannel.emit(xTwoChannel12, xTwoChannel22, XINCTwoChannel1[0], XINCTwoChannel2[0],
                                                 XREFTwoChannel1[0], XREFTwoChannel2[0],
                                                 maxTwoChannel1, minTwoChannel1, rmsTwoChannel1, maxTwoChannel2,
                                                 minTwoChannel2, rmsTwoChannel2, frqTwoChannel1[0], frqTwoChannel2[0],
                                                 P, S, Q)
            else:
                break

            if isChecked:
                if maxTwoChannel1 >= MaxValue or maxTwoChannel2 >= MaxValue:
                    break

            if ModeTwoCh == 0:
                break

    # funkcja wywoływana w momencie zatrzymania porcedury wielowątkowości
    def stop(self):
        self.isRunning = False

    # funkcja pobierająca aktualnie wybrany tryb pracy
    def getMode(self, value):
        global ModeTwoCh
        ModeTwoCh = value

    # funkcja pobierająca aktualną wartość wyzwalania
    def getMaxValue(self, value):
        global MaxValueTwoCh
        MaxValueTwoCh = value

    # funkcja pobierająca aktualny stan widgetów RadioButtonOn/Off
    def isOnChacked(self, OnChecked):
        global isCheckedTwoCh
        isCheckedTwoCh = OnChecked


app = QtWidgets.QApplication(sys.argv)
mainWindow = Oscilloscope()
mainWindow.show()
sys.exit(app.exec())
