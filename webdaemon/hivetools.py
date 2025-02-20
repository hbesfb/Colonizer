import cv2
import openvino as ov
import numpy as np
import supervision as sv

# settings
threshold_confidence = 0.2
threshold_IoU = 0.5

# load model
core = ov.Core()
model = core.read_model("./models/cfu_counts/best.xml")
batch, bpp, size_x, size_y = model.inputs[0].shape
cmodel = core.compile_model(model)

# load image
def detect_cfu(img : np.ndarray):
   img = img.astype(np.float32)
   img = cv2.resize(img, [size_x,size_y], interpolation=cv2.INTER_LINEAR)
   img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
   img /= 255
   img_tensor = img.T[np.newaxis]

   # run inference
   result = cmodel(img_tensor)[cmodel.output()][0].T

   # only use detections above confidence threshold
   indexes = np.where(result[:,4:]>threshold_confidence)[0]
   thresholded = result[indexes].T
   # convert xy center & width and height to corners
   xyxy = thresholded[0:4]
   xyxy[0:2] -= xyxy[2:4]*0.5
   xyxy[2:4] += xyxy[0:2]
   #
   label = np.argmax(thresholded[4:],axis=0).astype(np.intc)
   confidence = np.choose(label,thresholded[4:])
   detections = sv.Detections(xyxy.T,confidence=confidence,class_id=label)
   detections_nms = detections.with_nms(threshold=threshold_IoU)
   
   # print results
   labels = ['single', 'multi', 'bubble']
   cfu_arr = []
   for i,d in enumerate(detections_nms):
      bbox,_,c,l,*_ = d
      bbox /= np.array([size_x,size_y,size_x,size_y],np.float32)
      bbox = [round(float(x),4) for x in bbox]
      cfu = {
         'cert'      : round(float(c),2),
         'bbox'      : bbox,
         'label'     : int(l),
         'id'        : i,
         'override'  : False
      }
      cfu_arr.append(cfu)
   cfu_arr.sort(key=cfu_size)
   
   return cfu_arr

def cfu_size(cfu):
   return (cfu['bbox'][2] - cfu['bbox'][0]) * (cfu['bbox'][1] - cfu['bbox'][3])
