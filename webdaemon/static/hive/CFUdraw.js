var cfu_arr;
var results;
var model;
var show_low = true;
var threshold_low = 0.15;
var threshold_high = 0.20;
const labels = ['Unused', 'CFU', 'MultiCFU', 'Bubble', 'Dish']
console.log("CFU-draw - initialized")

// trigger on image load to set aspect ratio of overlay
$(document).ready(function() {
   cfu_setAspect();
   $("#image").on('load', cfu_setAspect);
});

// if image to overlay isn't square, compensate by setting viewbox as cfu coordinates are on relative to image width and height
function cfu_setAspect() {
   let img = $("#image").get(0);
   let ratio = img.naturalWidth / img.naturalHeight;
   let x1,x2,y1,y2;
   x1 = y1 = 0.0;
   x2 = y2 = 1.0;
   if (ratio > 1-0) {
      y2 = ratio;
   } else if (ratio < 1.0) {
      x2 = 1/ratio;
   } else {
      return
   }
   let vb = `${x1.toFixed(3)} ${y1.toFixed(3)} ${x2.toFixed(3)} ${y2.toFixed(3)}`;
   $("#overlay").attr('viewBox', vb);
   console.log("CFU-draw - fixed aspect ratio");
}

function cfu_toggle(id) {
   let element = document.getElementById(id);
   element.classList.toggle('CFU-positive');
   let index = Number(id.split('-')[1]);
   cfu_arr[index].override = !cfu_arr[index].override;
   console.log(index);
   cfu_update_counts();
}

function cfu_clear() {
   $('#overlay').empty();
   //$('#Counts').val(0);
}

function cfu_add(cfu) {
   const radius = 0.2;
   let [ymin,xmin,ymax,xmax] = cfu.bbox;
   let width = xmax-xmin;
   let height = ymax-ymin;
   let rect = $(document.createElementNS("http://www.w3.org/2000/svg", "rect"));
   let text = $(document.createElementNS("http://www.w3.org/2000/svg", "text"));
   let group = $(document.createElementNS("http://www.w3.org/2000/svg", "g"));

   rect.attr({
      x: xmin,
      y: ymin,
      width: width.toFixed(4),
      height: height.toFixed(4),
      rx: (Math.min(width,height)*radius).toFixed(4)
   });

   text.attr({
      x: (xmin+xmax)/2,
      y: (ymin+ymax)/2
   });
   text.text(`${(cfu.cert*100).toFixed(0)}%`);

   group.addClass("CFU");
   group.attr('id', `CFU-${cfu.id}`);
   group.click(function() { cfu_toggle(this.id); });
   group.append(rect);
   group.append(text);
   if ((cfu.cert >= threshold_high) | cfu.override) (
      group.addClass('CFU-positive')
   )

   $('#overlay').append(group);
}

function cfu_update_counts() {
   let n_cfus = $('.CFU-positive').length
   $("#Counts").val(n_cfus);
}

function cfu_export() {
   let cfu_json = []
   $('.CFU-positive').each(function() {
      index = Number($(this)[0].id.split('-')[1]);
      cfu_json.push(cfu_arr[index]);
   })
   return JSON.stringify(cfu_json);
}

function cfu_import(jsondata) {
   cfu_clear();
   cfu_arr = JSON.parse(jsondata);
   cfu_arr.forEach(cfu => {
      cfu_add(cfu);
   });
   // counts should be same as in db, if not it has been set manually and should be kept
   //cfu_update_counts();
}