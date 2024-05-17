import dlib, cv2, math, os, tempfile, uuid
from naja_atra import request_map, error_message, MultipartFile, StaticFile, Response, PathValue, Redirect, HttpError, server
from datetime import datetime

def display_rectangle(gray, face):
	cv2.rectangle(gray, (face.left(),face.top()), (face.right(), face.bottom()), (255, 255, 255), 3)

def display_number(gray, face, i):
	text = str(i)
	fontFace = cv2.FONT_HERSHEY_SIMPLEX
	fontScale = 1
	thickness = 3
	textSize = cv2.getTextSize(text, fontFace, fontScale, thickness)
	cv2.putText(gray, text, (int((face.right()-face.left())/2) - int(int(textSize[0][0])/2) + face.left(), face.bottom() + int(textSize[0][1])), fontFace, fontScale, (255, 255, 255),thickness)

def face_la_plus_proche(faces, faceRef):
	plusProche = min(faces, key=lambda face: 10000 if face.top() < faceRef.bottom() else math.sqrt((face.top() - faceRef.bottom())**2 + (face.left() - faceRef.left())**2))
	if plusProche.top() < faceRef.bottom():
		return
	else:
		return plusProche

def face_la_plus_haute(faces):
	return min(faces, key=lambda face: face.top())

def number(inputFile, outputFile, increment):
	gray = cv2.imread(inputFile, cv2.IMREAD_COLOR)
	face_detect = dlib.get_frontal_face_detector()

	rects = face_detect(gray, 1)

	faces = []
	for (i, rect) in enumerate(rects):
		faces.append(rect)

	faceNumber = increment
	while len(faces) > 0 :
		facesRestantes = []
		ligneCourante = []
		faceLaPlusHaute = face_la_plus_haute(faces)
		faceLaPlusProche = face_la_plus_proche(faces, faceLaPlusHaute)
		for face in faces:
			if faceLaPlusProche is None or face.bottom() < faceLaPlusProche.top():
				ligneCourante.append(face)
			else:
				facesRestantes.append(face)
		ligneCourante.sort(key=lambda face: face.left())
		
		for face in ligneCourante:
			display_number(gray, face, faceNumber)
			faceNumber += increment
		faces = facesRestantes
		
	cv2.imwrite(outputFile, gray)
    
@request_map("/upload", method="POST")
def upload(increment: str, img=MultipartFile("input")):
	date = datetime.today().strftime('%Y%m%d')
	uuidGenerated = str(uuid.uuid4())
	directoryPath = '/var/storage/' + date[0:4] + '/' + date[4:6] + '/' + date[6:8]
	print(directoryPath)
	os.makedirs(directoryPath, exist_ok=True)
	if img.content_type == 'image/png':
		extension = '.png'
	else:
		extension = '.jpg'
	inputFile = directoryPath + '/' + uuidGenerated + extension
	img.save_to_file(inputFile)
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
	number(inputFile, outputFile, int(increment))
	in_file = open(outputFile, "rb")
	data = in_file.read()
	in_file.close()
	
	return Response(200, {
		'Content-Type': ['image/jpeg'],
		'Content-Disposition': ['inline; filename="' + uuidValue  + '_numerotee_' + increment + '.jpg'+ '"']
	}, data)

@request_map("/", method="GET")
def index():
	root = os.path.dirname(os.path.abspath(__file__))
	return StaticFile("%s/index.html" % root, "text/html; charset=utf-8")

@request_map("/index.js", method="GET")
def favicon():
	root = os.path.dirname(os.path.abspath(__file__))
	return StaticFile("%s/index.js" % root, "text/javascript; charset=utf-8")

@request_map("/favicon.ico", method="GET")
def indexJS():
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