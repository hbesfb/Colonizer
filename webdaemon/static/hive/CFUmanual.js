document.addEventListener('DOMContentLoaded', () => {
	// --- 1. State Variables ---
	const overlay = document.getElementById('overlay');
   const image = document.getElementById('image');
   const clamp = (val, min=0, max=1) => Math.max(min, Math.min(max, val)); // function for clamping values
	let isDrawing = false;
	let startX = 0;
	let startY = 0;
	let currentGroup = null; // New: To hold the <g> element
	let currentRect = null;

	// --- 2. Event Listeners ---
	
	document.addEventListener('keydown', handleKeyDown);
	document.addEventListener('keyup', handleKeyUp);
	window.addEventListener('blur', handleWindowBlur);
	overlay.addEventListener('mousedown', handleMouseDown);
	overlay.addEventListener('mousemove', handleMouseMove);
	document.addEventListener('mouseup', handleMouseUp);

	// --- 3. Event Handler Functions ---

	function handleKeyDown(e) {
		if (e.key === 'Control') {
			overlay.classList.add('drawing-mode');
		}
	}

	function handleKeyUp(e) {
		if (e.key === 'Control') {
			overlay.classList.remove('drawing-mode');
		}
	}

	function handleWindowBlur() {
		// Safety catch if the window loses focus while Ctrl is pressed
		overlay.classList.remove('drawing-mode');
	}

	function handleMouseDown(e) {
		if (e.button !== 0 || !e.ctrlKey) return;
		
		e.preventDefault(); 
		
		isDrawing = true;
		const coords = getNormalizedCoordinates(e);
		startX = coords.x;
		startY = coords.y;

		// 1. Create the <g> wrapper and add your class
		currentGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
		currentGroup.setAttribute('class', 'CFU CFU-draw');

		// 2. Create the <rect> without the class (it will inherit from the group)
		currentRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
		currentRect.setAttribute('x', startX);
		currentRect.setAttribute('y', startY);
		currentRect.setAttribute('width', 0);
		currentRect.setAttribute('height', 0);
		
		// 3. Assemble and add to DOM
		currentGroup.appendChild(currentRect);
		overlay.appendChild(currentGroup);
	}

	function handleMouseMove(e) {
		if (!isDrawing || !currentRect) return;

		const coords = getNormalizedCoordinates(e);
		const radius = 0.2;
		const currentX = Math.min(startX, coords.x);
		const currentY = Math.min(startY, coords.y);
		const width = Math.abs(coords.x - startX);
		const height = Math.abs(coords.y - startY);

		currentRect.setAttribute('x', currentX);
		currentRect.setAttribute('y', currentY);
		currentRect.setAttribute('width', width);
		currentRect.setAttribute('height', height);
		//currentRect.setAttribute('rx', (Math.min(width,height)*radius).toFixed(4));
	}

	function handleMouseUp() {
		if (isDrawing && currentRect && currentGroup) {
			isDrawing = false;
			
			const finalX = parseFloat(currentRect.getAttribute('x'));
			const finalY = parseFloat(currentRect.getAttribute('y'));
			const finalWidth = parseFloat(currentRect.getAttribute('width'));
			const finalHeight = parseFloat(currentRect.getAttribute('height'));

			// Remove the whole group from the DOM
			overlay.removeChild(currentGroup);
			
			// Pass the coordinates to your processing function
			processRectangleCoordinates(finalX, finalY, finalWidth, finalHeight);
			
			currentRect = null; 
			currentGroup = null;
		}
	}

	// --- 4. Helper Function ---
	function getNormalizedCoordinates(e) {
		const bounds = image.getBoundingClientRect();
		const x = clamp(e.offsetX / bounds.width);
		const y = clamp(e.offsetY / bounds.height);
		return { x, y };
	}
});

// --- 5. External Processing Logic ---

function processRectangleCoordinates(normX, normY, normWidth, normHeight) {
	const img = document.getElementById('image');
	const nw = img.naturalWidth;
	const nh = img.naturalHeight;

	// 1. Convert normalized coordinates to actual image pixels
	const px = Math.floor(normX * nw);
	const py = Math.floor(normY * nh);
	const pWidth = Math.floor(normWidth * nw);
	const pHeight = Math.floor(normHeight * nh);

	if (pWidth <= 0 || pHeight <= 0) return;

	// 2. Extract the crop using a hidden canvas
	const canvas = document.createElement('canvas');
	canvas.width = pWidth;
	canvas.height = pHeight;
	const ctx = canvas.getContext('2d', { willReadFrequently: true });
	// Increase the pixel value (e.g., 'blur(4px)') if the mold lines are thick
	ctx.filter = 'blur(4px)';
	ctx.drawImage(img, px, py, pWidth, pHeight, 0, 0, pWidth, pHeight);
	
	const imgData = ctx.getImageData(0, 0, pWidth, pHeight).data;
	const totalPixels = pWidth * pHeight;
	
	// 3. Convert to grayscale and build histogram
	const gray = new Uint8Array(totalPixels);
	const hist = new Array(256).fill(0);
	
	for (let i = 0; i < totalPixels; i++) {
		// Luminance formula: 0.299 R + 0.587 G + 0.114 B
		const val = Math.round(
			0.299 * imgData[i*4] + 
			0.587 * imgData[i*4 + 1] + 
			0.114 * imgData[i*4 + 2]
		);
		gray[i] = val;
		hist[val]++;
	}

	// 4. Find the threshold using Otsu's Method
	const threshold = getOtsuThreshold(hist, totalPixels);

	// 5. Determine if the background is lighter or darker than the CFU
	// We assume the outer edges of the crop are mostly background (agar)
	let edgeSum = 0, edgeCount = 0;
	for (let x = 0; x < pWidth; x++) { 
		edgeSum += gray[x] + gray[(pHeight - 1) * pWidth + x]; 
		edgeCount += 2; 
	}
	const bgMean = edgeSum / edgeCount;
	const cfuIsLighter = bgMean < threshold;

	// 6. Scan the crop to find the tightest bounds of the CFU
	let minX = pWidth, minY = pHeight, maxX = 0, maxY = 0;
	let cfuFound = false;

	for (let y = 0; y < pHeight; y++) {
		for (let x = 0; x < pWidth; x++) {
			const val = gray[y * pWidth + x];
			// Check if the pixel belongs to the CFU based on our threshold
			const isCFU = cfuIsLighter ? (val >= threshold) : (val <= threshold);
			
			if (isCFU) {
				if (x < minX) minX = x;
				if (x > maxX) maxX = x;
				if (y < minY) minY = y;
				if (y > maxY) maxY = y;
				cfuFound = true;
			}
		}
	}

	if (!cfuFound) {
		console.warn("No CFU detected within the selection.");
		return;
	}

	// 7. Convert the tightened pixel bounds back to normalized (0-1) coordinates
	const tightNormX = round4((px + minX) / nw);
	const tightNormY = round4((py + minY) / nh);
	const tightNormWidth = round4((maxX - minX) / nw);
	const tightNormHeight = round4((maxY - minY) / nh);

	// 8. Check for overlapping existing CFUs
	const newBbox = [tightNormY, tightNormX, tightNormY + tightNormHeight, tightNormX + tightNormWidth];
	const newArea = tightNormWidth * tightNormHeight;
	
	let maxOverlap = 0.50; // Maximum 50% overlap
	let overlappingIds = [];

	for (const id in cfus) {
		const [eYmin, eXmin, eYmax, eXmax] = cfus[id].bbox;
		const existArea = (eYmax - eYmin) * (eXmax - eXmin);
		
		// Calculate intersection width and height
		const iWidth = Math.max(0, Math.min(newBbox[3], eXmax) - Math.max(newBbox[1], eXmin));
		const iHeight = Math.max(0, Math.min(newBbox[2], eYmax) - Math.max(newBbox[0], eYmin));
		const intersectionArea = iWidth * iHeight;
		
		if (intersectionArea > 0) {
			// Overlap % relative to the smaller of the two boxes
			const overlapPercent = intersectionArea / Math.min(newArea, existArea);
			
			if (overlapPercent > maxOverlap) {
				overlappingIds.push(id);
			}
		}
	}

	// 9. If overlap is greater than 50%, delete the existing CFU
	console.log(`Replacing existing CFU: ${overlappingIds.join(',')}`);
		for (const id of overlappingIds) {
	  // Remove from DOM
		const oldElement = document.getElementById(`CFU-${id}`);
		if (oldElement) oldElement.remove();
		
		// Remove from state and update counts
		delete cfus[id];
	}

	// Create the final object. (Matching your existing cfu_add format)
	const newCFU = {
		cert: 1.00,      // Manual additions get 100% certainty
		id: cfu_newid(), // Generate a unique ID
		label: 0,
		bbox: [tightNormY, tightNormX, tightNormY + tightNormHeight, tightNormX + tightNormWidth], 
		override: true
	};
	
	cfu_add(newCFU);
	cfu_update_counts();
}

function round4(number) {
   return Math.round(number*1e4)/1e4
}

// Otsu's Method: A fast, elegant algorithm to split a bimodal histogram
function getOtsuThreshold(hist, total) {
	let sum = 0;
	for (let t = 0; t < 256; t++) sum += t * hist[t];
	
	let sumB = 0, wB = 0, wF = 0;
	let varMax = 0, threshold = 0;

	for (let t = 0; t < 256; t++) {
		wB += hist[t];                  // Weight Background
		if (wB === 0) continue;
		
		wF = total - wB;                // Weight Foreground
		if (wF === 0) break;
		
		sumB += t * hist[t];
		
		const mB = sumB / wB;           // Mean Background
		const mF = (sum - sumB) / wF;   // Mean Foreground
		
		// Calculate Between Class Variance
		const varBetween = wB * wF * (mB - mF) * (mB - mF);
		
		// Check if new maximum found
		if (varBetween > varMax) {
			varMax = varBetween;
			threshold = t;
		}
	}
	return threshold;
}