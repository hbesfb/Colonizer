var new_batch;
var new_serial;
var new_location;
var text_input;
var batch_locations;
var positive_batch;
var positive_location;
var positive_serial;

const GLYPH = {
   WAIT: 'wait',
   PASS: 'pass',
   FAIL: 'fail',
   ACTIVE: 'active'
}

const STATE = {
   RESET:    'reset',
   BATCH:    'batch',
   SERIAL:   'serial',
   LOCATION: 'location',
   REGISTER: 'register',
   LOOP:     'loop'
};

var state = STATE.BATCH;

// ----------------------
// STATE MACHINE
// ----------------------
function transition(new_state) {
   console.log(`New state: ${new_state}`);

   switch(new_state) {

      case STATE.BATCH:
         new_batch=null;
         new_serial=null;
         new_location=null;
         text_input = "";
         $("#barcode").val(text_input);
         $("#duplicate").slideUp();
         update_fields();
         update_table();
         set_glyph($("#batch_glyph"),GLYPH.ACTIVE);
         set_glyph($("#serial_glyph"),GLYPH.WAIT);
         set_glyph($("#location_glyph"),GLYPH.WAIT);
         set_glyph($("#input_glyph"),GLYPH.ACTIVE);
         state=STATE.BATCH;
         break;

      case STATE.LOOP:
         new_serial=null;
         new_location=null;
         set_glyph($("#location_glyph"),GLYPH.WAIT);
         state = STATE.LOOP;
         break;

      case STATE.SERIAL:
         update_fields();
         update_table();
         set_glyph($("#batch_glyph"),GLYPH.PASS);
         set_glyph($("#serial_glyph"),GLYPH.ACTIVE);
         state=STATE.SERIAL;
         break;

      case STATE.LOCATION:
         update_fields();
         set_glyph($("#serial_glyph"),GLYPH.PASS);
         set_glyph($("#location_glyph"),GLYPH.ACTIVE);
         state=STATE.LOCATION;
         break;

      case STATE.REGISTER:
         set_glyph($("#location_glyph"),GLYPH.PASS);
         state=STATE.REGISTER;
         register_new();
         break;
   }
}

// ----------------------
// INPUT PROCESSING
// ----------------------
function process_input(data) {

   if ("location" in data && state !== STATE.LOCATION) {
      console.log("Ignoring unexpected location scan");
      return;
   }

   if (data.no_positive) return;

   switch(state) {

      case STATE.BATCH:
         if("batch" in data) {
            new_batch = data.batch;
            transition(STATE.SERIAL);
         }
         break;

      case STATE.SERIAL:
         if("serial" in data) {

            if(data.used > 0) {
               $("#duplicate-plate").slideDown();
               return;
            }

            $("#duplicate-plate").slideUp();
            new_serial = data.serial;
            transition(STATE.LOCATION);
         }
         break;

      case STATE.LOCATION:
         if("location" in data) {
            if (location_exist(data["location"])) {
               $("#duplicate-location").slideDown();
            } else {
               $("#duplicate-location").slideUp();
               $("#expired-plate").slideUp();
               new_location = data.location;
               transition(STATE.REGISTER);
            }
         }
         break;
   }
}

// ----------------------
// HELPERS
// ----------------------
function update_fields() {
   if (new_serial !== null) $("#serial").val(new_serial);
   if (new_batch !== null) $("#batch").val(new_batch);
   if (new_location !== null) $("#location").val(new_location);
}

// ----------------------
// AJAX: REGISTER
// ----------------------
function register_new() {
   if(new_batch && new_serial && new_location) {
      $.ajax({
         type: "POST",
         contentType: "application/json; charset=utf-8",
         url: "/settleplate/register",
         data: JSON.stringify({batch:new_batch, serial:new_serial, location:new_location}),
         success: function (data) {
            console.log(data);
            setTimeout(() => transition(STATE.LOOP), 1000);
         },
         error: function (XMLHttpRequest, textStatus, errorThrown) {
            alert("Registration error - Status: " + textStatus + "\nError: " + errorThrown);
            transition(STATE.BATCH);
         },
         dataType: "json"
      });
   }
}

// ----------------------
// AJAX: PARSE
// ----------------------
function decode_text() {
   $.ajax({
      type: "POST",
      contentType: "application/json; charset=utf-8",
      url: "/parse",
      data: JSON.stringify(text_input),
      success: function (data) {
         check_positive(data);
         process_input(data);
      },
      dataType: "json"
   });
}

// ----------------------
// EVENT HANDLERS
// ----------------------
$(document).ready(function() {

   $(document).keypress(function(event) {
      var k = event.which || event.keyCode;
      var c = String.fromCharCode(k);
      text_input = text_input + c;
      $("#barcode").val(text_input);
   });

   $(document).keydown(function(event) {
      if(event.keyCode == 13) {
         decode_text();
         text_input = "";
      }
   });

   $('#no-positive-link').on("click", register_positive);

   transition(STATE.BATCH);
});