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
});

function on_load() {
   $("#camera").removeClass("imageview-loading");
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
            $("#save_ok").html(`<strong>Success!</strong> Image saved to <i>${data.filename}</i>`)
            $("#save_ok").slideDown();
         } else {
            $("#save_ok").slideUp();
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