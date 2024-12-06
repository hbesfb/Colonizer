var model;
var index_n;
var index_cert;
var index_bbox;
var index_label;

async function cfu_load_model() {
   let model_url = "/static/hive/model_2.0/model.json"
   model = await tf.loadGraphModel(model_url);
   // run first with zeros so everything is ready, reducing lag the first time
   let primer = tf.zeros([1,640,640,3], dtype='int32');
   await model.executeAsync(primer);
   console.log('CFU-detect - initialized');
   // bind and enable button when loaded
   $('#detect').on('click', cfu_detect)
   $('#detect').prop('disabled', false);
   index_n = model.outputNodes.indexOf("num_detections");
   index_cert = model.outputNodes.indexOf("Identity_4:0");
   index_bbox = model.outputNodes.indexOf("detection_boxes");
   index_label = model.outputNodes.indexOf("Identity_2:0");
};

async function cfu_detect() {
   let start = Date.now()

   let img_element = document.getElementById('image');
   let img_orig = tf.browser.fromPixels(img_element);
   let img_resized = tf.image.resizeBilinear(img_orig,[640,640]);
   let input_tensor = tf.cast(img_resized, dtype='int32').expandDims() ;
   let output_tensor = await model.executeAsync(input_tensor);

   let n = output_tensor[index_n].arraySync()[0]
   
   // clear overlay
   cfu_clear();

   cfu_arr = [];
   for (let i=0;i<n;i++) {
      let cfu = {
         cert : +output_tensor[index_cert].arraySync()[0][i].toFixed(2), // + to convert from string to number again
         bbox : output_tensor[index_bbox].arraySync()[0][i].map(item => +item.toFixed(4)),
         label : labels[Number(output_tensor[index_label].arraySync()[0][i])],
         id: i,
         override : false
      }
      // skip if below threshold1
      if (cfu.cert < threshold_low) { break; }
      if (cfu.cert < threshold_high && !show_low) { continue; }
      // if not add to array and draw rectangles and labels
      cfu_arr.push(cfu);
   }
   // sort by size so largest is drawn first, so mouse over works as intended
   cfu_sorted = cfu_arr.slice().sort(cfu_compare);
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
