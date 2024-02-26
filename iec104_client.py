import socket
import threading
import logging
import time
import queue


class IEC104_Client:
    def __init__(self, rt_host, rt_port, cheat_mode=False):
        # TCP connection
        self.rt_host = rt_host
        self.rt_port = rt_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Banderas
        self.cheat_mode = cheat_mode  # Bandera para activar el modo "cheat"
        self.shutdown_flag = threading.Event()
        self.startdt_received = threading.Event()
        # contadores
        self.receive_sequence_number = 0
        # Contador de marcos I recibidos desde el último marco S enviado
        self.frames_since_last_s_frame = 0
        # Número máximo de marcos I antes de enviar un marco S
        self.max_frames_before_s_frame = 5
        # marcas de tiempo
        self.connection_start_time = None  # Tiempo de inicio de la conexión
        self.connection_end_time = None  # Tiempo de finalización de la conexión
        self.last_i_frame_sent_time = None  # Para T1
        self.last_i_frame_received_time = None  # Para T2
        self.last_frame_sent_or_received_time = None  # Para T3
        self.waiting_for_startdt_con = False  # Para T0
        self.t0 = 30
        self.t1 = 15
        self.t2 = 10
        self.t3 = 20
        # almacenamiento
        self.data_queue = queue.Queue()

        # Definiciones de marcos U
        self.startdt_act = b'\x68\x04\x07\x00\x00\x00'
        self.startdt_con = b'\x68\x04\x0B\x00\x00\x00'
        self.testfr_act = b'\x68\x04\x43\x00\x00\x00'
        self.testfr_con = b'\x68\x04\x83\x00\x00\x00'
        self.stopdt_act = b'\x68\x04\x13\x00\x00\x00'
        self.stopdt_con = b'\x68\x04\x23\x00\x00\x00'

        # Configuración de logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s')
    
    def is_stopped(self):
        return self.shutdown_flag.is_set()

    def receiver_thread(self):
        while not self.shutdown_flag.is_set():
            try:
                response = self.sock.recv(1024)
                if not response:
                    logging.info("Connection closed by remote host, attempting to reconnect...")
                    self.reconnect()  # Intenta reconectar
                    break
                self.response_handler(response)
            except socket.error as e:
                logging.exception(f"Socket error occurred: {e}, attempting to reconnect...")
                self.reconnect()  # Intenta reconectar
                break
            except Exception as e:
                logging.exception(f"Unexpected error in receiver_thread: {e}")
                break
        logging.info("Receiver thread exiting")

    def response_handler(self, response):
        if response.startswith(self.startdt_con):
            self.last_frame_sent_or_received_time = time.time()
            self.startdt_received.set()
            self.waiting_for_startdt_con = False
            logging.info("STARTDT_CON received, communication established")

        elif response[2] & 0x01 == 0:  # I Frame
            # if self.last_i_frame_received_time == None:
            #    self.last_i_frame_received_time = time.time()
            # logging.info(response)
            # Actualiza la marca de tiempo del ultimo I recibido
            self.last_i_frame_received_time = time.time()
            ssn = ((response[2] & 0xfe) >> 1) | (
                response[3] << 7)  # Captura el último SSN recibido
            self.last_ssn_received = ssn  # Actualiza el último SSN recibido
            self.data_queue.put(response)  # Agrega el frame a la cola
            self.receive_sequence_number += 1  # Actualiza el RSN del cliente
            self.send_s_frame()  # Enviar S frame en respuesta
            # logging.info(f"Received I frame with SSN: {ssn}")

            # Comparar el SSN con el RSN para detectar discrepancias
            if self.cheat_mode:
                if ssn != self.last_ssn_received:
                    # logging.warning(f"Discrepancy detected: SSN {ssn} does not match RSN {self.last_ssn_received}")
                    pass
            else:
                if ssn != self.receive_sequence_number:
                    # logging.warning(f"Discrepancy detected: SSN {ssn} does not match RSN {self.receive_sequence_number}")
                    pass

        elif response == self.testfr_con:
            logging.info(f"Received frame: TESTFR_CON")

        else:
            logging.info(f"Received frame: {response.hex()}")

        self.last_frame_sent_or_received_time = time.time()

    def timeouts_handler(self):
        while not self.shutdown_flag.is_set():
            try:
                current_time = time.time()

                # T0: Timeout de establecimiento de conexión
                if self.waiting_for_startdt_con and (current_time - self.connection_start_time > self.t0):
                    logging.error(
                        "T0 timeout: No STARTDT_CON received. Reconnecting...")
                    # self.reconnect()

                # T1: Timeout de confirmación de tramas I
                if self.last_i_frame_sent_time and (current_time - self.last_i_frame_sent_time > self.t1):
                    logging.warning(
                        "T1 timeout: No acknowledgment for I frame. Retransmitting...")
                    # self.retransmit_last_i_frame()

                # T2: Timeout de no recepción de tramas I //OK
                if self.last_i_frame_received_time and (current_time - self.last_i_frame_received_time > self.t2):
                    logging.info(
                        "T2 timeout: Sending S frame as acknowledgment.")
                    self.send_s_frame()

                # T3: Timeout de prueba de enlace //OK
                if self.last_frame_sent_or_received_time and (current_time - self.last_frame_sent_or_received_time > self.t3):
                    logging.info(
                        "T3 timeout: Sending TESTFR_ACT to keep the connection alive.")
                    self.send_u_frame(self.testfr_act)

                time.sleep(1)  # Ajusta este valor según sea necesario
            except Exception as e:
                logging.error(f"Timeouts handler error: {e}")
                break  # Salir del bucle en caso de error
        logging.info("Timeouts handler exiting")

    def send_u_frame(self, u_frame):
        try:
            self.sock.sendall(u_frame)
            logging.info(f"Sent U frame: {u_frame.hex()}")
            self.last_frame_sent_or_received_time = time.time()
        except Exception as e:
            logging.error(f"Error sending U frame: {e}")

    def send_s_frame(self):
        if self.cheat_mode:
            rsn = self.last_ssn_received  # En modo "cheat", usa el último SSN recibido como RSN
        else:
            # Incrementa el último SSN recibido para el RSN en modo normal
            rsn = (self.receive_sequence_number) % 32768

        cf3 = (rsn << 1) & 0xFF
        cf4 = (rsn >> 7) & 0xFF
        s_frame = bytes([0x68, 0x04, 0x01, 0x00, cf3, cf4])
        try:
            self.sock.sendall(s_frame)
            # logging.info(f"Sent S frame with RSN: {rsn}")
        except Exception as e:
            logging.error(f"Error sending S frame: {e}")
        finally:
            self.last_frame_sent_or_received_time = time.time()

    def start(self):
        # Asegúrate de establecer esto al inicio de start()
        self.connection_start_time = time.time()
        self.waiting_for_startdt_con = True
        try:
            self.sock.connect((self.rt_host, self.rt_port))
            logging.info("Connection established")
            threading.Thread(target=self.receiver_thread).start()
            threading.Thread(target=self.timeouts_handler).start()
            self.send_u_frame(self.startdt_act)
        except Exception as e:
            logging.error(f"Connection error: {e}")
            self.shutdown_flag.set()

    def stop(self):
        logging.info("Stopping client...")

        # Envía la señal de cierre a los subprocesos
        self.shutdown_flag.set()

        # Cierra la conexión de red enviando el marco stopdt_act
        try:
            self.send_u_frame(self.stopdt_act)
        except Exception as e:
            logging.error(f"Error sending STOPDT_ACT frame: {e}")

        # Cierra el socket
        try:
            self.sock.close()
        except Exception as e:
            logging.error(f"Error closing socket: {e}")

        # Espera a que los subprocesos terminen
        for thread in threading.enumerate():
            # Asegúrate de que sea uno de tus hilos
            if thread.name.startswith("Thread"):
                logging.info(f"Waiting for {thread.name} to finish...")
                thread.join()

        logging.info("Client stopped")

    def get_frame(self):
        """Recupera un marco I de la cola."""
        try:
            # Ajusta el timeout según sea necesario
            frame = self.data_queue.get(timeout=1)
            return frame
        except queue.Empty:
            print("No frames available in queue.")
            return None

    def get_queue_size(self):
        return self.data_queue.qsize()
    
    def reconnect(self):
        logging.info("Attempting to reconnect...")
        self.shutdown_flag.clear()  
        try:
            self.sock.close()  # Cierra el socket actual 
        except Exception as e:
            logging.error(f"Error closing socket during reconnection: {e}")

        while not self.shutdown_flag.is_set():
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Crea un nuevo socket
                self.sock.connect((self.rt_host, self.rt_port))  # Intenta reconectar
                logging.info("Reconnected successfully")
                self.startdt_received.clear()  # Restablece la señal de STARTDT_CON
                threading.Thread(target=self.receiver_thread).start()  # Reinicia el hilo receptor
                threading.Thread(target=self.timeouts_handler).start()  # Reinicia el manejo de timeouts
                self.send_u_frame(self.startdt_act)  # Envía STARTDT_ACT para reiniciar la comunicación
                break  # Sale del bucle si la reconexión es exitosa
            except Exception as e:
                logging.error(f"Reconnection failed: {e}, retrying in 5 seconds...")
                time.sleep(5)  #
