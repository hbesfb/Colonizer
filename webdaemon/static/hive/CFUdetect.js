var model;
var max_cfus = 200;
var threshold_iou = 0.4;    // max area overlap
var threshold_low = 0.10;   // min score to include CFU
var size_x;
var size_y;

var labels = [ "CFU_single", "CFU_multi", "bubble" ];

async function cfu_load_model() {
   let model_url = "/static/hive/yolo_v1.0/model.json"
   model = await tf.loadGraphModel(model_url);
   size_x = model.inputs[0].shape[1];
   size_y = model.inputs[0].shape[2];

   // run first with zeros so everything is ready, reducing lag the first time
   let primer = tf.zeros([1,size_x,size_y,3], dtype='float32');
   await model.executeAsync(primer);
   console.log('CFU-detect - initialized');
   // bind and enable button when loaded
   $('#detect').on('click', cfu_detect)
   $('#detect').prop('disabled', false);
};

async function cfu_detect() {
   let start = Date.now()

   // clear overlay and cfu array
   cfu_clear();
   cfu_arr = [];

   // get image and convert to tensor
   let img_element = document.getElementById('image');
   let img_orig = tf.browser.fromPixels(img_element);
   let img_resized = tf.image.resizeBilinear(img_orig,[size_x,size_y]);
   let input_tensor = tf.cast(img_resized.div(255), dtype='float32').expandDims();

   // run inference, and get first (only) output tensor
   let output_tensor = await model.executeAsync(input_tensor);
   output_tensor = output_tensor.gather(0);

   // convert cfu center and width/height to corner coordinates
   let x1 = output_tensor.gather(1);
   let y1 = output_tensor.gather(0);
   let x2 = output_tensor.gather(3);
   let y2 = output_tensor.gather(2);
   let half = tf.scalar(0.5,tf.float32);
   x1 = x1.sub(x2.mul(half));
   y1 = y1.sub(y2.mul(half));
   x2 = x1.add(x2);
   y2 = y1.add(y2);
   let x_div = tf.scalar(size_x,tf.float32);
   let y_div = tf.scalar(size_y,tf.float32);
   x1 = x1.div(x_div);
   y1 = y1.div(y_div);
   x2 = x2.div(x_div);
   y2 = y2.div(y_div);
   
   // set input arrays for NMS and run NMS to threshold and remove overlapping CFUs
   let boxes = tf.stack([x1,y1,x2,y2],axis=1);
   let scores  = output_tensor.gather(4);
   let indexes = await tf.image.nonMaxSuppressionAsync(boxes, scores, max_cfus, threshold_iou, threshold_low);

   // generate output array
   //let n_labels = output_tensor.shape[0]-4;
   //for (let l=0; l<n_labels; l++) {
   //   scores = output_tensor.gather(l+4);
   //   indexes = await tf.image.nonMaxSuppressionAsync(boxes, scores, max_cfus, threshold_iou, threshold_low);
      indexes.arraySync().forEach(function(idx, i) {
         let cfu = {
            cert : +scores.gather(idx).arraySync().toFixed(2), // + to convert from string to number again
            bbox : boxes.gather(idx).arraySync().map(n => +n.toFixed(4)),
            label : 0,
            id: i,
            override : false
         }
         cfu_arr.push(cfu);
      });
   //}
   // sort by size so largest is drawn first, so mouse over works as intended
   let cfu_sorted = cfu_arr.slice().sort(cfu_compare);
   for (let i=0;i<cfu_sorted.length;i++) {
      cfu_add(cfu_sorted[i]);
   }

   let end = Date.now()
   console.log(`Execution time ${end-start} ms`);

   cfu_update_counts();
}


function cfu_compare(a,b) {
   a_size = (a.bbox[2] - a.bbox[0]) * (a.bbox[1] - a.bbox[3])
   b_size = (b.bbox[2] - b.bbox[0]) * (b.bbox[1] - b.bbox[3])
   
   if (a_size < b_size) {
      return -1;
   }
   if (a_size > b_size) {
      return 1;
   }
   return 0;
}

// load ML-model
$(document).ready(function() {
   cfu_load_model();
});
