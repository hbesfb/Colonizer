import cv2
import math
import numpy as np

def get_circle(image, settings):
	h,w, *_ = image.shape
	c_x = settings["crop_mask_cx"]
	c_y = settings["crop_mask_cy"]
	c_r = settings["crop_mask_cr"]
	circle_x = int(w*c_x)
	circle_y = int(h*c_y)
	circle_r = int(h*c_r)
	return circle_x, circle_y, circle_r     

def gen_mask(image, settings):
	h,w, *_ = image.shape
	circle_x, circle_y, circle_r = get_circle(image, settings)
	mask = np.zeros([h,w], dtype=np.uint8)
	cv2.circle(mask, (circle_x, circle_y), circle_r, 1, -1)
	return mask

def draw_mask(image, settings):
	circle_x, circle_y, circle_r = get_circle(image, settings)
	cv2.circle(image, (circle_x, circle_y), circle_r, (0,255,0), 5)
	return image

def prep_img(image, factor=1.0):
	height, width, *_ = image.shape
	newsize = (int(width/factor),int(height/factor))
	resized = cv2.resize(image, newsize)
	blurred = cv2.GaussianBlur(resized, ksize=(9,9), sigmaX=0)
	return blurred

def make_lower_left(box):
	"""
	lay_down ensure that the first corner is the lower left
	: param box: box that describes the rectangle
	"""
	# sort coordinates to find lower left
	lower_two = box[:, 1].argsort()[2:4] # find index of highest two y values
	lower_left = box[lower_two, 0].argsort()[0] # find index of lowest x value within the two y-indices
	index = lower_two[lower_left]

	# shift box coordinates so lower left is first
	box = np.roll(box,-index,axis=0)
	return box

def lay_down(box):
	"""
	lay_down moves first corner to ensure minimum rotation of rectangle
	: param box: box that describes the rectangle
	"""
	box = make_lower_left(box)
	v = box[0] - box[1]
	t = math.atan2(v[0],v[1])/np.pi*180
	if t > 45:
		box = np.roll(box,-1,axis=0)
	return box

def crop_rect(image, box):
	# get length of sides
	l1 = np.linalg.norm(box[0]-box[1])
	l2 = np.linalg.norm(box[2]-box[1])
	# set src and dest triangles
	src = np.float32(box[0:3])
	dst = np.float32([[0,l1], [0,0], [l2,0]])
	# do transform
	m_crop = cv2.getAffineTransform(src, dst)
	img_crop =  cv2.warpAffine(image, m_crop, (int(l2), int(l1)))
	return img_crop

def to_jpg(image):
	params = list()
	params.append(cv2.IMWRITE_JPEG_QUALITY)
	params.append(90) # compression level
	ret, image_encoded = cv2.imencode('.jpg', image, params)
	return image_encoded.tobytes()

def to_png(image):
	params = list()
	params.append(cv2.IMWRITE_PNG_COMPRESSION)
	params.append(9) # compression level
	ret, image_encoded = cv2.imencode('.png', image, params)
	return image_encoded.tobytes()

def mask_image(img_org, settings):
	if settings['crop_drawonly']:
		return draw_mask(img_org, settings)
	mask = gen_mask(img_org, settings)
	img_masked = img_org * mask[...,None]
	return img_masked

def autocrop_rect(img_org, settings):
	# reduce image size for speed
	factor = 8

	# resize and blur
	img_prep = prep_img(img_org, factor)
	mask = gen_mask(img_prep, settings)

	# detect edges
	t1 = settings["crop_canny_t1"]
	t2 = settings["crop_canny_t2"]
	img_canny = cv2.Canny(img_prep,t1,t2)
	img_canny_masked = img_canny * mask
	contours, *_ = cv2.findContours(img_canny,cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

	# if too few edges found, return None
	if len(contours) < 1:
		if settings['crop_drawonly']:
			draw_mask(img_canny_masked, settings)
			return img_canny_masked
		else:
			return img_org

	# sort contours by increasing size, and choose largest contour
	#contour = sorted(contours, key=cv2.contourArea)[-1]
	contour = sorted(contours, key=lambda x: cv2.arcLength(x,True))[-1]
	# use this to generate cropping rectangle
	(cx,cy),(sx,sy),r = cv2.minAreaRect(contour) # center, size and rotation
	rect = ((cx*factor,cy*factor),(sx*factor,sy*factor),r) # scale center and size
	box = np.intp(np.round(cv2.boxPoints(rect),0))
	box = lay_down(box)

	if settings['crop_drawonly']:
		canny_rgb = cv2.cvtColor(img_canny_masked,cv2.COLOR_GRAY2RGB)
		img = cv2.resize(canny_rgb, (img_org.shape[0],img_org.shape[1]), interpolation = cv2.INTER_NEAREST)
		draw_mask(img, settings)
		thickness = int(round(img.shape[0]*0.002,0))
		cv2.drawContours(img, [box],0,(255,0,255),thickness)
		cv2.circle(img,(box[0][0],box[0,1]),thickness*3,(0,0,255),-1)
		img = cv2.addWeighted(img_org, 0.5, img, 1.0, 1.0)
		return img

	img = crop_rect(img_org, box)

	return img

def autocrop_ring(img_org, settings):
	# reduce image size for speed
	factor = 8

	# use gray only
	img_gray = cv2.cvtColor(img_org, cv2.COLOR_RGB2GRAY)
	#if img_gray.dtype == np.uint16:
	#	img_gray = (img_gray/256).astype('uint8')

	# resize and blur
	img_prep = prep_img(img_gray, factor)
	mask = gen_mask(img_prep)

	# detect edges, threshold and mask
	img_thrs = cv2.adaptiveThreshold(img_prep, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 10)
	img_thrs_masked = img_thrs * mask
	edges = np.transpose(np.nonzero(img_thrs_masked))
	
	# get circle parameters and scale to full size
	(mask_x, mask_y), mask_r = cv2.minEnclosingCircle(edges)
	mask_x = int(mask_x * factor+0.5)
	mask_y = int(mask_y * factor+0.5)
	mask_r = int(mask_r * factor+0.5)

	x1 = max(mask_x-mask_r, 0)
	x2 = min(mask_x+mask_r, img_org.shape[0])
	y1 = max(mask_y-mask_r, 0)
	y2 = min(mask_y+mask_r, img_org.shape[1])

	# if too small radius (<30%) or too much off center, fail
	min_radius = 0.2
	#max_outside = 0.3
	min_axis = min(img_org.shape[0:1])
	rel_r = mask_r / min_axis # size of r relative to shortest axis
	#rel_x = abs((mask_x / min_axis) - 0.5)*2
	#rel_y = abs((mask_y / min_axis) - 0.5)*2

	if rel_r < min_radius:
		return img_org
	
	# set pizels outside circle to color
	mask = np.zeros_like(img_org)
	cv2.circle(mask, (mask_y, mask_x), mask_r, [0,0,0], -1)
	img_out = cv2.bitwise_and(img_org, mask)
	img_out = img_out[x1:x2, y1:y2]

	return img_out

def auto_level(img):
	# histogram equalization
	img_yuv = cv2.cvtColor(img, cv2.COLOR_RGB2YUV)
	clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
	img_yuv[:,:,0] = clahe.apply(img_yuv[:,:,0])
	return cv2.cvtColor(img_yuv, cv2.COLOR_YUV2RGB)

def rotate_image(image, settings):
	rotation = settings['cam_rotation'].lower()
	if rotation == 'cw':
		dir = cv2.ROTATE_90_CLOCKWISE
	elif rotation == 'ccw':
		dir = cv2.ROTATE_90_COUNTERCLOCKWISE
	elif rotation == '180':
		dir = cv2.ROTATE_180
	else:
		return image
	return cv2.rotate(image, dir)

def draw_histogram(image: np.ndarray) -> np.ndarray:
	# draw in upper right corner
	width = int(image.shape[0] * 0.2)
	height = int(width/2)
	margin = int(width*0.05)

	x2 = image.shape[0] - margin
	x1 = x2 - width
	y1 = margin
	y2 = y1 + height
	# copy part of image to draw on
	hist_image = image[y1:y2,x1:x2]
	white_rect = np.ones(hist_image.shape, dtype=np.uint8) * 255
	hist_image = cv2.addWeighted(hist_image, 0.7, white_rect, 0.3, 1.0)
	# calculate histogram
	for channel, color in enumerate(([255,0,0],[0,255,0],[0,0,255])):
		ch_img = np.zeros_like(hist_image)
		# calc histogram
		bins = np.linspace(0,1,256)
		hist = cv2.calcHist([image], [channel], None, [256], [0,256])[:,0]
		# normalize
		hist = hist / np.max(hist[1:-1])
		hist = np.clip(hist,0,1)
		#
		bins = np.concatenate(( [0], bins, [1]))
		hist = np.concatenate(( [0], hist, [0]))
		# to pixel coord
		bins = (bins * (width-margin) + margin/2).round().astype(int)
		hist = (hist * (height-margin) + margin/2).round().astype(int)
		points = np.vstack((bins, height-hist)).T
		# draw
		#cv2.polylines(hist_image, [points], False, color)
		cv2.fillPoly(ch_img, [points], color)
		hist_image = cv2.addWeighted(hist_image, 1.0, ch_img, 0.5, 1.0)

	image[y1:y2,x1:x2] = hist_image
	return image