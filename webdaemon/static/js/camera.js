const image_capture = "/images/live"

function refresh_image() {
   let url=image_capture + "?mode=" + $("#mode").val() + "&" +new Date().getTime();
   $("#camera").addClass("imageview-loading")
   $("#camera-img").attr("src", url);
}

$(document).ready(function() {
   // load image on startup
   refresh_image();
   // setup events
   $("#refresh").on("click", refresh_image);
   $("#mode").on("change", refresh_image);
   $("#save").on("click", save_image);
   $("#camera-img").on("load", on_load);
   // zoom in on image on click
   $("#camera-img").click(function () {
      $("#imagemodal").modal('show');
   });
   // when new image loaded, update imagezoom
   $("#camera-img").on('load', function() {
      $("#imagezoom").attr("src", $("#camera-img").attr("src"));
   })
   // ------------------------------------------------------------
   // Detect camera offline (404) and show a clear error banner
   // ------------------------------------------------------------
   $("#camera-img").on('error', function () {
      // Only handle errors for live camera captures
      if ($(this).attr("src").startsWith(image_capture)) {
         // Stop spinner
         $("#camera").removeClass("imageview-loading");

         // Show placeholder image
         $("#camera-img").attr("src", "/static/settleplate.svg");

         // Show user-friendly offline message
         $("#save_fail").html(`<strong>Error! </strong> Camera offline — cannot capture image.`);
         $("#save_fail").slideDown();

         // Disable Save button (no image available)
         $("#save").prop("disabled", true);

         // Optional: Disable Refresh button (refresh cannot succeed)
         $("#refresh").prop("disabled", true);

         // Hide success banner if visible
         $("#save_ok").slideUp();

         // Auto-hide banners after timeout
         slideup_all();
      }
   });
});

function on_load() {
   $("#camera").removeClass("imageview-loading"); // stop spinner to indicate nolonger "loading"

   // Don't re-enable buttons if this "load" is just the offline placeholder
   // ie load fired only because the placeholder SVG itself loaded fine, not because the camera worked.
   if ($("#camera-img").attr("src").endsWith("/static/settleplate.svg")) {
      return;
   }

   // re-enable buttons on a genuine successful load (ie pi online and image capture was successful)
   $("#save").prop("disabled", false);
   $("#refresh").prop("disabled", false);
}

function save_image() {
   $.ajax({
      type: "POST",
      contentType: "application/json; charset=utf-8",
      url: "/images/save",
      data: JSON.stringify({ batch: $("#batch").val() }),
      success: function (data) {
         console.log(data);
         if (data.saved == true) {
            $("#save_fail").slideUp();
            $("#save_ok").html(`<strong>Success!</strong> Image saved to <i>${data.filename}</i> on the Pi`)
            $("#save_ok").slideDown();
         } else {
            // Insert backend error message into the banner
            const msg = data.error || "Unknown error";
            $("#save_ok").slideUp();
            $("#save_fail").html(`<strong>Error!</strong> Failed to save image: ${msg}`);
            $("#save_fail").slideDown();
         }
         slideup_all();
      },
      dataType: "json"
   });
}

function slideup_all() {
   setTimeout(function () {
      $("#save_ok").slideUp();
      $("#save_fail").slideUp();
   }, 8000);
}