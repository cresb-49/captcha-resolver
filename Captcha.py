import os

from selenium import webdriver
from selenium.webdriver.common.by import By
import base64
import time
import easyocr
import cv2
import numpy as np


def eliminar_trazos_finos(imagen, umbral):
    # Convierte la imagen a escala de grises
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)

    # Aplica un umbral para binarizar la imagen
    _, binarizada = cv2.threshold(gris, umbral, 255, cv2.THRESH_BINARY)

    # Encuentra los contornos en la imagen binarizada
    contornos, _ = cv2.findContours(binarizada, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Crea una máscara para los trazos gruesos
    mascara_trazos_gruesos = np.zeros_like(gris)

    # Itera sobre los contornos y dibuja solo los contornos gruesos
    for contorno in contornos:
        perimetro = cv2.arcLength(contorno, True)
        if perimetro > umbral:  # Puedes ajustar este umbral según tus necesidades
            cv2.drawContours(mascara_trazos_gruesos, [contorno], -1, 255, thickness=cv2.FILLED)

    # Aplica la máscara a la imagen original
    resultado = cv2.bitwise_and(imagen, imagen, mask=mascara_trazos_gruesos)

    return resultado

options = webdriver.ChromeOptions()
options.add_experimental_option("detach", True)

driver = webdriver.Chrome(options=options)

driver.get("https://portal.sat.gob.gt/portal/calendario-tributario/")

time.sleep(2)
# Debemos de cambiar al iframe donde se encuentra el captcha
driver.switch_to.frame(0)

captchaBool = False

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

        # Especifica el umbral para trazos gruesos (puedes ajustar este valor)
        umbral_trazos_gruesos = 100

        # Aplica el tratamiento de la imagen
        imagen_procesada = eliminar_trazos_finos(imagen, umbral_trazos_gruesos)

        # Muestra la imagen original y la imagen procesada
        cv2.imshow("Imagen Original", imagen)
        cv2.imshow("Imagen Procesada", imagen_procesada)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

        # Leemos la imagen del captcha
        reader = easyocr.Reader(['en'])
        result = reader.readtext('captcha.jpg')
        text = result[0][1]
        print(text)

        driver.find_element(By.XPATH, '//*[@id="calendario:txtRespuesta"]').send_keys(text)
        driver.find_element(By.XPATH, '//*[@id="calendario:btnCaptcha"]').click()
        # Eliminamos la imagen del captcha
        os.remove("captcha.jpg")
        time.sleep(3)
        # Print del traceback del error
    except Exception as e:
        print("Volviendo a intentar el captcha")
        print(e)

calendario = driver.find_element(By.XPATH, '//*[@id="calendario:data"]')

filas = calendario.find_elements(By.TAG_NAME, "tr")

datos = []
for fila in filas:
    columnas = fila.find_elements(By.TAG_NAME, "td")
    datos.append([celda.text for celda in columnas])

for dato in datos:
    print(dato)