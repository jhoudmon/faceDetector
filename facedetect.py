import cv2, math, os, tempfile, uuid, subprocess, magic
from naja_atra import request_map, error_message, MultipartFile, StaticFile, Response, PathValue, Redirect, HttpError, server
from datetime import datetime
from mtcnn_cv2 import MTCNN

MINIMUM_WIDTH_FOR_NUMEROTATION = 2400


def copy_all_metadata(source_path, target_path):
	subprocess.run([
		"exiftool",
		"-overwrite_original",
		"-TagsFromFile", source_path,
		"-all:all",
		"-unsafe",
		target_path
	], check=True)

def display_rectangle(gray, face):
	if False:
		cv2.rectangle(gray, (face['left'],face['top']), (face['right'], face['bottom']), (255, 255, 255), 3)

def display_number(gray, face, i):
	text = str(i)

	fontFace = cv2.FONT_HERSHEY_SIMPLEX
	thickness = 2
	targetFontHeight = (face['bottom'] - face['top']) / 4
	standardFontHeight = cv2.getTextSize(text, fontFace, 1, thickness)
	fontScale = targetFontHeight / int(standardFontHeight[0][1])
	
	textSize = cv2.getTextSize(text, fontFace, fontScale, thickness)
	rectangleSpace = int((face['bottom'] - face['top'])/3)
	cv2.circle(
		gray,
		(
			face['left'] + int((face['right']-face['left'])/2),
			face['bottom'] + rectangleSpace + int(textSize[0][1] / 2)
		),
		textSize[0][1],
		(255, 255, 255),
		-1
	)
	cv2.putText(
		gray,
		text, 
		(	
			int((face['right']-face['left'])/2) - int(int(textSize[0][0])/2) + face['left'], 
   			face['bottom'] + int(textSize[0][1]) + rectangleSpace
		),
		fontFace,
		fontScale,
		(0, 0, 0),
		thickness
	)

def face_la_plus_proche(faces, faceRef):
	plusProche = min(faces, key=lambda face: 10000 if face['top'] < faceRef['bottom'] else math.sqrt((face['top'] - faceRef['bottom'])**2 + (face['left'] - faceRef['left'])**2))
	if plusProche['top'] < faceRef['bottom']:
		return None
	else:
		return plusProche

def face_la_plus_haute(faces):
	return min(faces, key=lambda face: face['top'])

def number_with_opencv(inputFile, outputFile, increment):
	img = cv2.imread(inputFile, cv2.IMREAD_COLOR)

	if (img.shape[1] < MINIMUM_WIDTH_FOR_NUMEROTATION):
		img = cv2.resize(img, (MINIMUM_WIDTH_FOR_NUMEROTATION, int(img.shape[0] * MINIMUM_WIDTH_FOR_NUMEROTATION / img.shape[1])), interpolation = cv2.INTER_LINEAR)
	
	detector = MTCNN()
	rects = detector.detect_faces(img)

	faces = []

	for result in rects:
		x, y, w, h = result['box']
		faces.append({
			'left': x,
			'top': y,
			'bottom': y + h,
			'right': x + w
		})
	

	faceNumber = increment
	while len(faces) > 0 :
		facesRestantes = []
		ligneCourante = []
		faceLaPlusHaute = face_la_plus_haute(faces)
		faceLaPlusProche = face_la_plus_proche(faces, faceLaPlusHaute)
		for face in faces:
			if faceLaPlusProche is None or face['bottom'] <= faceLaPlusProche['top']:
				ligneCourante.append(face)
			else:
				facesRestantes.append(face)
		ligneCourante.sort(key=lambda face: face['left'])
		
		for face in ligneCourante:
			display_number(img, face, faceNumber)
			display_rectangle(img, face)
			faceNumber += increment
		faces = facesRestantes
		
	cv2.imwrite(outputFile, img)
	
	copy_all_metadata(inputFile, outputFile)
    
@request_map("/upload", method="POST")
def upload(increment: str, img=MultipartFile("input")):
	
	date = datetime.today().strftime('%Y%m%d')
	uuidGenerated = str(uuid.uuid4())
	directoryPath = '/var/storage/' + date[0:4] + '/' + date[4:6] + '/' + date[6:8]
	os.makedirs(directoryPath, exist_ok=True)
	inputFile = directoryPath + '/' + uuidGenerated
	img.save_to_file(inputFile)
	mime = magic.from_file(inputFile, mime=True)
	if mime not in ['image/jpeg', 'image/png']:
		os.unlink(inputFile)
		raise HttpError(400, "Type MIME non supporté")

	extension = '.jpg' if mime == 'image/jpeg' else '.png'
	os.rename(inputFile, inputFile + extension)
	return Redirect("/photo/%s/%s/numerotee/%s" % (uuidGenerated, date, increment))

@request_map("/photo/{uuid}/{date}/originale")
def downloadOriginale(uuidValue=PathValue("uuid"), date=PathValue("date")):
	inputFileWithoutExtension = '/var/storage/' + date[0:4] + '/' + date[4:6] + '/' + date[6:8] + '/' + uuidValue
	if os.path.isfile(inputFileWithoutExtension + '.png'):
		contentType = 'image/png'
		extension = '.png'
	elif os.path.isfile(inputFileWithoutExtension + '.jpg'):
		contentType = 'image/jpeg'
		extension = '.jpg'
	else:
		raise HttpError(404, "Photo inexistante")
	inputFile = inputFileWithoutExtension + extension
	in_file = open(inputFile, "rb")
	data = in_file.read()
	in_file.close()
	
	return Response(200, {
		'Content-Type': [contentType],
		'Content-Disposition': ['inline; filename="' + uuidValue  + extension + '"']
	}, data)

@request_map("/photo/{uuid}/{date}/numerotee/{increment}")
def downloadNumerotee(uuidValue=PathValue("uuid"), date=PathValue("date"), increment=PathValue("increment")):
	inputFileWithoutExtension = '/var/storage/' + date[0:4] + '/' + date[4:6] + '/' + date[6:8] + '/' + uuidValue
	if os.path.isfile(inputFileWithoutExtension + '.png'):
		inputFile = inputFileWithoutExtension + '.png'
	elif os.path.isfile(inputFileWithoutExtension + '.jpg'):
		inputFile = inputFileWithoutExtension + '.jpg'
	else:
		raise HttpError(404, "Photo inexistante")
	outputFile = tempfile.mktemp('.jpg')
	number_with_opencv(inputFile, outputFile, int(increment))
	in_file = open(outputFile, "rb")
	data = in_file.read()
	in_file.close()
	os.unlink(outputFile)
	
	return Response(200, {
		'Content-Type': ['image/jpeg'],
		'Content-Disposition': ['inline; filename="' + uuidValue  + '_numerotee_' + increment + '.jpg'+ '"']
	}, data)

@request_map("/", method="GET")
def index():
	root = os.path.dirname(os.path.abspath(__file__))
	return StaticFile("%s/index.html" % root, "text/html; charset=utf-8")

@request_map("/index.js", method="GET")
def indexJS():
	root = os.path.dirname(os.path.abspath(__file__))
	return StaticFile("%s/index.js" % root, "text/javascript; charset=utf-8")

@request_map("/favicon.ico", method="GET")
def favicon():
	root = os.path.dirname(os.path.abspath(__file__))
	return StaticFile("%s/favicon.ico" % root, "image/x-icon")

@error_message("404", "403")
def my_40x_page(code, message, explain=""):
	root = os.path.dirname(os.path.abspath(__file__))
	return StaticFile("%s/error404.html" % root, "text/html; charset=utf-8")

@error_message
def error_message(code, message, explain=""):
	root = os.path.dirname(os.path.abspath(__file__))
	return StaticFile("%s/error.html" % root, "text/html; charset=utf-8")

server.start(port=8000)

#docker build -t facedetector .
#docker run -it --rm --name facedetector -p8000:8000 -v "$PWD":/usr/src/app facedetector