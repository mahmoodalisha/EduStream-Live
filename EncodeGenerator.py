import cv2
import face_recognition
import pickle
import os


def encodeGenerator():

    #import user images as list
    print(os.listdir("."))
    folderPath = os.path.abspath("uploads")
    pathList = os.listdir(folderPath)
    imgList = []
    studentIds = []
    for path in pathList:
        imgList.append(cv2.imread(os.path.join(folderPath,path)))

        studentIds.append(os.path.splitext(path)[0])




    # funtion for encoding
    def findEncodings(imagesList):
        encodeList = []
        for img in imagesList:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            encode = face_recognition.face_encodings(img)[0]
            encodeList.append(encode)
        return encodeList




    #calling encoding funtion
    print("Encoding started..")
    encodeListKnown = findEncodings(imgList)
    encodeListKnownWithIds = [encodeListKnown, studentIds]
    print("Encoding Complete...")



    #saving encoding into a achar file
    file = open("Encodefile.p", 'wb')
    pickle.dump(encodeListKnownWithIds, file)
    file.close()
    print("File saved...")
