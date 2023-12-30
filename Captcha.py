import os
import traceback

from selenium import webdriver
from selenium.webdriver.common.by import By
import base64
import time
import easyocr
import cv2
import imutils
import numpy as np


def procesado_imagen(image):
    try:
        # Cargamos la imagen, y la convertimos a escala de grises.
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Aplicamos thresholding automático con el algoritmo de Otsu. ESto hará que el texto se vea blanco, y los elementos
        # del fondo sean menos prominentes.
        thresholded = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
        # cv2.imshow("Otsu", thresholded)
        # cv2.waitKey(0)

        # Calculamos y normalizamos la transformada de distancia.
        dist = cv2.distanceTransform(thresholded, cv2.DIST_L2, 5)
        dist = cv2.normalize(dist, dist, 0, 1.0, cv2.NORM_MINMAX)
        dist = (dist * 255).astype("uint8")

        # cv2.imshow("Dist", dist)
        # cv2.waitKey(0)

        # Aplicamos thresholding al resultado de la operación anterior, y mostramos el resultado en pantalla.
        dist = cv2.threshold(dist, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        # cv2.imshow('Dist Otsu', dist)
        # cv2.waitKey(0)

        # Aplicamos apertura para desconectar manchas y blobs de los elementos que nos interesan (los números)
        # El valor del argumento ksize (#,#) se puede ajustar para que se adapte a las necesidades de cada caso.
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        opening = cv2.morphologyEx(dist, cv2.MORPH_OPEN, kernel)
        # cv2.imshow('Apertura', opening)
        # cv2.waitKey(0)

        # Hallamos los contornos de los caracteres de la imagen.
        contours = cv2.findContours(opening.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = imutils.grab_contours(contours)

        chars = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            # Solo los contornos grandes perdurarán, ya que corresponden a los caracteres que nos interesan.
            # El valor de comparacion de w y h se puede ajustar para que se adapte a las necesidades de cada caso.
            if w >= 5 and h >= 15:
                chars.append(contour)

        # Hallamos la cáscara convexa que envuelve todos los números.
        chars = np.vstack([chars[i] for i in range(0, len(chars))])
        hull = cv2.convexHull(chars)

        # Creamos una máscara y la alargamos.
        mask = np.zeros(image.shape[:2], dtype='uint8')
        cv2.drawContours(mask, [hull], -1, 255, -1)
        mask = cv2.dilate(mask, None, iterations=2)
        # cv2.imshow('MASCARA', mask)
        # cv2.waitKey(0)

        # Aplicamos la máscara para aislar los números del fondo.
        final = cv2.bitwise_and(opening, opening, mask=mask)
    except Exception as e:
        final = image
        traceback.print_exc()
    return final


options = webdriver.ChromeOptions()
options.add_experimental_option("detach", True)

driver = webdriver.Chrome(options=options)

# URL de la página, de la cual se obtendrá el captcha
driver.get("https://portal.sat.gob.gt/portal/calendario-tributario/")

time.sleep(2)

# Debemos de cambiar al iframe donde se encuentra el captcha
driver.switch_to.frame(0)

captchaBool = False

# Numero de intentos para pasar el captcha
intentos = 0

while not captchaBool:
    try:
        captcha = None
        try:
            # Verificamos si la imagen del existe mediante el xpath
            captcha = driver.find_element(By.XPATH, '//*[@id="calendario:validaTxt"]')
        except Exception as e:
            print("No se encontró el captcha")
            captchaBool = True
            break
        # Obtenemos la imagen del captcha
        captchaImage = driver.find_element(By.XPATH, '//*[@id="calendario:validaTxt"]')

        captchaImageSave = driver.execute_async_script("""
            var ele = arguments[0], callback = arguments[1];
            ele.addEventListener('load', function fn(){
              ele.removeEventListener('load', fn, false);
              var cnv = document.createElement('canvas');
              cnv.width = this.width; cnv.height = this.height;
              cnv.getContext('2d').drawImage(this, 0, 0);
              callback(cnv.toDataURL('image/jpeg').substring(22));
            }, false);
            ele.dispatchEvent(new Event('load'));
            """, captchaImage)

        time.sleep(5)

        # Guardamos la imagen en un archivo
        with open(r"captcha.jpg", 'wb') as f:
            f.write(base64.b64decode(captchaImageSave))

        # Carga la imagen
        imagen = cv2.imread("captcha.jpg")

        # Aplica el tratamiento de la imagen
        imagen_procesada = procesado_imagen(imagen)

        # Muestra la imagen original y la imagen procesada
        # cv2.imshow("Imagen Original", imagen)
        # cv2.imshow("Imagen Procesada", imagen_procesada)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()
        # Guarda la imagen procesada
        cv2.imwrite("captcha2.jpg", imagen_procesada)
        # Filtro de caracteres
        allowlist = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        # Leemos la imagen del captcha
        reader = easyocr.Reader(['en'])
        result = reader.readtext('captcha2.jpg', allowlist=allowlist)
        text = result[0][1]
        print("Posible solucion:", text)

        driver.find_element(By.XPATH, '//*[@id="calendario:txtRespuesta"]').send_keys(text)
        driver.find_element(By.XPATH, '//*[@id="calendario:btnCaptcha"]').click()
        # Eliminamos la imagen del captcha
        os.remove("captcha.jpg")
        os.remove("captcha2.jpg")
        intentos += 1
        time.sleep(4)
        # Print del traceback del error
    except IndexError as e:
        # Es posible de easyocr no reconozca el captcha correctamente
        # En ese caso se debe de volver a intentar, enviando un string vacio
        print("El captcha no se pudo leer correctamente")
        driver.find_element(By.XPATH, '//*[@id="calendario:txtRespuesta"]').send_keys("")
        driver.find_element(By.XPATH, '//*[@id="calendario:btnCaptcha"]').click()
    except Exception as e:
        # En caso de que el error sea otro, se debe de volver a intentar
        print("Volviendo a intentar el captcha")
        traceback.print_exc()


# Si se logra pasar el captcha, se procede a obtener los datos de la pagina despues del captcha
if captchaBool:
    print(f"El captcha se resolvio en {intentos} intentos")
    # Aqui igual debemos de manejar Excepciones por si no se encuentra el elemento
    try:
        calendario = driver.find_element(By.XPATH, '//*[@id="calendario:data"]')

        filas = calendario.find_elements(By.TAG_NAME, "tr")

        datos = []
        for fila in filas:
            columnas = fila.find_elements(By.TAG_NAME, "td")
            datos.append([celda.text for celda in columnas])

        for dato in datos:
            print(dato)
    except Exception as e:
        print("No se encontró el calendario")
        traceback.print_exc()
else:
    print(f"No se pudo resolver el captcha, hubo {intentos} intentos")