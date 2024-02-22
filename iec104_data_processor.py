from iec104_definitions import ASDU_TYPES, ELEMENTS_LENGTHS
import datetime
import struct
import logging


class IEC104DataProcessor:
    def __init__(self, element_lengths, asdu_types_df):
        self.element_lengths = element_lengths
        self.asdu_types_df = asdu_types_df

    @staticmethod
    def decode_information_objects(asdu, type_id, sq, num_objects):
        objects = []

        # Encuentra la definición de ASDU correspondiente al type_id
        asdu_definition = next(
            (item for item in ASDU_TYPES if str(item['Type']) == str(type_id)), None)

        if asdu_definition:
            # Si se trata de un tipo de ASDU reservado o no definido
            if type_id >= 127:
                pass  # Manejar según sea necesario
            else:
                object_length = int(asdu_definition['elements_len'])
                current_index = 0

                if sq == 0:  # Información de objeto individual
                    while current_index < len(asdu) and len(objects) < num_objects:
                        # Identificador de objeto de información
                        ioa = asdu[current_index:current_index+3]
                        object_info = asdu[current_index +
                                           3:current_index+3+object_length]
                        objects.append({'ioa': ioa, 'info': object_info})
                        current_index += 3 + object_length
                else:  # Información de objeto secuencial
                    ioa = asdu[current_index:current_index+3]
                    current_index += 3
                    for _ in range(num_objects):
                        if current_index < len(asdu):
                            object_info = asdu[current_index:current_index+object_length]
                            objects.append({'ioa': ioa, 'info': object_info})
                            current_index += object_length

        return objects

    @staticmethod
    def decode_apdu(apdu):
        """
        Decodifica la APDU, extrayendo y procesando el ASDU contenido.
        """
        # Asumimos que los primeros 6 bytes son APCI y el resto es ASDU
        asdu = apdu[6:]  # Extrae el ASDU de la APDU

        # Ahora procesamos el ASDU como antes
        type_id = asdu[0]  # Type Identification
        sq = (asdu[1] >> 7) & 0x01  # SQ bit
        num_objects = asdu[1] & 0x7F  # Number of Objects
        t = (asdu[2] >> 7) & 0x01  # T bit
        pn = (asdu[2] >> 6) & 0x01  # P/N bit
        cot = asdu[2] & 0x3F  # COT
        originator_address = asdu[3]
        asdu_address = asdu[4] + (asdu[5] << 8)  # Asumiendo endian little

        # Decodificar los objetos de información utilizando la función previamente definida
        objects = IEC104DataProcessor.decode_information_objects(
            asdu[6:], type_id, sq, num_objects)

        return {
            'type_id': type_id,
            'sq': sq,
            'num_objects': num_objects,
            't': t,
            'pn': pn,
            'cot': cot,
            'originator_address': originator_address,
            'asdu_address': asdu_address,
            'objects': IEC104DataProcessor.decode_information_objects(asdu[6:], type_id, sq, num_objects)
        }

    @staticmethod
    def cp56time2a_to_mysql_timestamp(cp56time2a):
        if not isinstance(cp56time2a, bytes) or len(cp56time2a) != 7:
            raise ValueError("Input must be a 7-byte array.")

        # Unpack the CP56Time2a bytes
        milliseconds = int.from_bytes(
            cp56time2a[0:2], byteorder='little') & 0x3FFF
        minute = cp56time2a[2] & 0x3F
        hour = cp56time2a[3] & 0x1F
        day = cp56time2a[4] & 0x1F
        month = cp56time2a[5] & 0x0F
        year = cp56time2a[6] + 2000  # Assuming the year is 2000 +

        # Create a datetime object
        dt = datetime.datetime(year, month, day, hour, minute,
                               milliseconds // 1000, (milliseconds % 1000) * 1000)

        # Format the datetime object as a MySQL timestamp
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def decode_information_objects(asdu, type_id, sq, num_objects):
        objects = []
        decoded_objects = []  # Lista para almacenar objetos decodificados

        # Encuentra la definición de ASDU correspondiente al type_id
        asdu_definition = next(
            (item for item in ASDU_TYPES if str(item['Type']) == str(type_id)), None)

        if asdu_definition:
            if type_id >= 127:
                pass  # Manejar según sea necesario
            else:
                object_length = int(asdu_definition['elements_len'])
                current_index = 0

                if sq == 0:  # Información de objeto individual
                    while current_index < len(asdu) and len(objects) < num_objects:
                        ioa = asdu[current_index:current_index+3]
                        object_info = asdu[current_index +
                                           3:current_index + 3 + object_length]
                        objects.append({'ioa': ioa, 'info': object_info})
                        current_index += 3 + object_length
                else:  # Información de objeto secuencial
                    ioa = asdu[current_index:current_index+3]
                    current_index += 3
                    for _ in range(num_objects):
                        if current_index < len(asdu):
                            object_info = asdu[current_index:current_index+object_length]
                            objects.append({'ioa': ioa, 'info': object_info})
                            current_index += object_length

        # Procesa cada objeto "info" si type_id es 36
        if type_id == 36:
            for obj in objects:
                structured_obj = IEC104DataProcessor.decode_object_structure(
                    type_id, obj["info"])
                if structured_obj:
                    decoded_objects.append({
                        # Convierte IOA a entero
                        'ioa': int.from_bytes(obj['ioa'], byteorder='little'),
                        **structured_obj  # Agrega los campos decodificados
                    })

        return decoded_objects  # Retorna la lista de objetos decodificados

    @staticmethod
    def decode_object_structure(type_id, object_info):
        asdu_definition = next(
            (item for item in ASDU_TYPES if str(item['Type']) == str(type_id)), None)

        if asdu_definition:
            structure = asdu_definition['Format'].split('+')
            structured_obj = {}
            current_index = 0

            for part in structure:
                part = part.strip()
                # Obtiene la longitud de la parte actual del diccionario element_lengths
                length = ELEMENTS_LENGTHS.get(part)
                if length is not None:
                    part_data = object_info[current_index:current_index+length]

                    if part == 'IEEE STD 754':
                        # Decodifica como un valor flotante IEEE 754
                        part_data = struct.unpack('<f', part_data)[0]
                    elif part == 'CP56Time2a':
                        part_data = IEC104DataProcessor.cp56time2a_to_mysql_timestamp(
                            part_data)  # Convierte CP56Time2a a un timestamp MySQL

                    structured_obj[part] = part_data
                    current_index += length
                else:
                    logging.warning(
                        f"Length not found for part: '{part}' in Type ID {type_id}")

            return structured_obj
        else:
            logging.info(f"No structure found for Type ID {type_id}")
            return None
