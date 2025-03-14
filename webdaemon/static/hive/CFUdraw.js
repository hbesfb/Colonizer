var cfus;
var results;
var model;
var show_low = true;
var rect_min_size = 0.015;
var threshold_high = 0.50;  // min threshold to count CFU automatically
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
   let cfu_id = Number(id.split('-')[1]);
   cfus[cfu_id].override = !cfus[cfu_id].override;
   console.log(cfu_id);
   cfu_update_counts();
}

function cfu_clear() {
   $('#overlay').empty();
   cfus = {};
   //$('#Counts').val(0);
}

function bbox_pad(bbox, minsize) {
   let [ymin,xmin,ymax,xmax] = bbox;
   let width = xmax-xmin;
   let height = ymax-ymin;
   let xpad = (Math.max(width, minsize)-width) / 2;
   let ypad = (Math.max(height, minsize)-height) / 2;
   return [ymin-ypad, xmin-xpad,ymax+ypad,xmax+xpad];
}

function cfu_add(cfu) {
   const radius = 0.2;
   let [ymin,xmin,ymax,xmax] = bbox_pad(cfu.bbox, rect_min_size);
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
   cfus[cfu.id] = cfu;
}

function cfu_update_counts() {
   let n_cfus = $('.CFU-positive').length
   $("#Counts").val(n_cfus);
}

function cfu_export() {
   let cfu_arr = []
   $('.CFU-positive').each(function() {
      cfu_id = Number($(this)[0].id.split('-')[1]);
      cfu_arr.push(cfus[cfu_id]);
   })
   return JSON.stringify(cfu_arr);
}

function cfu_import(jsondata) {
   cfu_clear();
   let cfu_arr = JSON.parse(jsondata);
   // convert from array to dictionary, add cfu to svg
   cfu_arr.forEach(cfu => {
      cfu_add(cfu);
   });
}