// initialize on load
const image_placeholder = "/static/settleplate.svg"
const image_capture = "/images/live?mode=settleplate"
var image_src = "";

$(document).ready(function() {
   init_page();

   // set up events
   $("#clear").click(init_page);

   // zoom in on image on click
   $("#zoom").click(function () {
      $("#imagemodal").modal('show');
   });
   // when new image loaded, update imagezoom
   $("#image").on('load', function() {
      if ($(this).attr("src") == image_src) {
         $("#imagezoom").attr("src", image_src);
      }
   })
   // script for capturing barcode reader input on screen
   // prevent submit on enter press
   $("#barcode").change(function (event) {
      $("#barcode").attr('readonly', true);
      decode_text($("#barcode").val());
   });
   // refresh image on button click
   $("#refresh").click(function () {
      cfu_clear();
      // as no-cache is ignored by browser, using cache-breaker
      image_src = image_capture + "&" +new Date().getTime();
      $("#image").attr("src", image_src);
      $("#Counts").attr("readonly", false);
   });

   $("#Counts").change(function (e) {
      $("#refresh").attr("disabled", true);
      $("#commit").attr("disabled", false);
      $("#commit").trigger("focus");
   });

   // commit image to db on click
   $("#commit").click(function () {
      $("#commit").attr("disabled", true);
      $("#Counts").attr('readonly', true);
      $("#commit").blur();
      $.ajax({
         type: "POST",
         contentType: "application/json; charset=utf-8",
         url: "/settleplate/scan",
         data: JSON.stringify({ barcode: $("#barcode").val(), counts: $("#Counts").val(), colonies: cfu_export()}),
         success: function (data) {
            console.log(data);
            if (data.committed == true) {
               $("#commit_fail").slideUp();
               $("#commit_ok").html(`<strong>Success!</strong> Image committed to DB`)
               $("#commit_ok").slideDown();
               table_append(data.ID, data.dT, data.Counts);
               setTimeout(init_page, 3000);
            } else {
               $("#commit_ok").slideUp();
               // Show specific error if provided by backend, otherwise fall back to generic message
               $("#commit_fail").html(`<strong>Error!</strong> ${data.error || 'Failed to commit image to DB'}`);
               $("#commit_fail").slideDown();
               // restore the UI to a usable state so user can recapture or rescan
               $("#refresh").prop("disabled", false);  // allow image recapture
               $("#Counts").prop("readonly", false); // allow counts to be changed again
               $("#barcode").prop("readonly", false);  // allow serial rescan
               $("#barcode").focus();
               $("#commit").prop("disabled", false); // allow commit/save retry
               slideup_all(); //moved here so it does not fire for both success and failure (when succeeded, init_page calls it anyways, so no need to call twice)
            }
         },
         dataType: "json"
      });
      
   });
});

function slideup_all() {
   setTimeout(function () {
      $("#commit_ok").slideUp();
      $("#commit_fail").slideUp();
      $("#sameuser_error").slideUp();
   }, 3000);
}

function decode_text(text_input) {
   console.log("Request barcode decode: " + text_input);
   $.ajax({
      type: "POST",
      contentType: "application/json; charset=utf-8",
      url: "/parse",
      data: JSON.stringify(text_input),
      success: function (data) {
         console.log(data);
         if ("serial" in data) {
            $("#barcode").val(data.serial)
            $("#image").attr("src", "/static/settleplate.svg") // reset image on new serial
            plate_info();
         }
      },
      dataType: "json"
   });
}

function plate_info() {
   $.ajax({
      type: "POST",
      contentType: "application/json; charset=utf-8",
      url: "/settleplate/info",
      data: JSON.stringify({ 'barcode': $("#barcode").val() }),
      success: function (data) {
         console.log(data);
         if ("error" in data) {
            $("#barcode").val("") // reset value in barcode and set focus
            alert(data.error);
            init_page();
         } else {
            $("#refresh").attr("disabled", false);
            $("#refresh").focus();
            $("#batch").val(data.Batch);
            $("#location").val(data.Location);
            $("#table_timepoints").empty();
            for (var i = 0; i < data.Timepoints.length; i++) {
               table_append(data.Timepoints[i].ID, data.Timepoints[i].dT, data.Timepoints[i].Counts);
            }
            if (data.SameUser) {
               $("#sameuser_error").slideDown();
            }
         }
      },
      dataType: "json"
   });
}

function table_append(ID, dT, Counts) {
   $("#table_timepoints").append(`
      <tr>
         <td><a href="${ID}" target="_blank">${ID}</a></td>
         <td>${dT}</td>
         <td>${Counts}</td>
      </tr>
   `);
}

function init_page() {
   $("#Counts").val("");
   $("#Counts").attr('readonly', true);
   $("#barcode").val("");
   $("#barcode").attr('readonly', false);
   $("#batch").val("");
   $("#location").val("");
   $("#table_timepoints").empty();
   $("#image").attr("src", image_placeholder);
   $("#imagezoom").attr("src", image_placeholder);
   $("#barcode").focus();
   $("#refresh").attr("disabled", true);
   $("#commit").attr("disabled", true);
   cfu_clear();
   slideup_all();
}
