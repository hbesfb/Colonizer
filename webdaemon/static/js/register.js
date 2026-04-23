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
}

// ============================================
// SHARED FUNCTIONS (used by both flows)
// ============================================
// transition state machine
function transition(new_state) {
   console.log(`New state: ${new_state}`);
   switch(new_state) {
      default:

      case STATE.BATCH:
         new_batch=null;
         new_serial=null;
         new_location=null;
         text_input = "";
         $("#barcode").val(text_input);
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
         // explicit transition instead of fallthrough, same behaviour as old
         transition(STATE.SERIAL);
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

function set_glyph(glyph, state) {
   glyph.toggleClass('fa-question-circle', state == GLYPH.WAIT);
   glyph.toggleClass('fa-check-circle', state == GLYPH.PASS);
   glyph.toggleClass('fa-exclamation-circle', state == GLYPH.FAIL);
}

function update_table(callback) {
   if(new_batch == null) {
      if(callback) callback();
      return;
   }
   $.ajax({
      type: "POST",
      contentType: "application/json; charset=utf-8",
      url: "/settleplate/batch_bydate",
      data: JSON.stringify({'batch':new_batch}),
      success: function (data) {
         batch_locations = data;
         console.log(batch_locations);
         $("#table_registered").empty();
         for(var i=0; i<batch_locations.length;i++) {
            $("#table_registered").append(`
               <tr>
                  <td>${batch_locations[i].ScanDate}</td>
                  <td>${batch_locations[i].Barcode}</td>
                  <td>${batch_locations[i].Location}</td>
               </tr>
            `)
         }
         if(callback) callback();
      },
      dataType: "json"
   });
}

function location_exist(location) {
   if (!batch_locations || !Array.isArray(batch_locations)) {
      console.warn("Batch locations not loaded yet");
      return false;
   }
   for(var i=0; i<batch_locations.length;i++) {
      if (location == batch_locations[i].Location)
         return true;
   }
   return false;
}

function update_fields() {
   $("#serial").val(new_serial);
   $("#location").val(new_location);
   $("#batch").val(new_batch);
}

function register_new() {
   if(new_batch != null && new_serial != null && new_location != null) {
      $.ajax({
         type: "POST",
         contentType: "application/json; charset=utf-8",
         url: "/settleplate/register",
         data: JSON.stringify({batch:new_batch, serial:new_serial, location:new_location}),
         success: function (data) {
            console.log(data);
            // when Backend did not commit to DB (but HTTP returns 200 even on failure eg for invalid_barcode and duplicate_barcode)
            if (!data.committed) {
               // Hide all alerts first
               reset_plate_errors();

               switch (data.reason) {
                  case "invalid_barcode":
                     show_all_other_alerts("Invalid barcode scanned.", "warning");
                     break;

                  default:
                     show_all_other_alerts("Registration failed: " + data.reason, "danger");
               }

               // Do NOT reset state — user must correct the issue
               return;
            }

            // Success - allow for input fields of last scan to show for the delay period before 
            // moving on to next plate
            setTimeout(function() {
               transition(STATE.LOOP);
            }, 2000);
         },
         error: function (xhr, textStatus, errorThrown) {
            // Try to parse JSON response from backend
            if (xhr.responseJSON) {
               const data = xhr.responseJSON;
               
               // Hide all alerts first
               reset_plate_errors();

               switch (data.reason) {
                  case "duplicate_location":
                     $("#duplicate-location").slideDown();
                     break;

                  case "duplicate_barcode":
                     $("#duplicate-plate").slideDown();
                     break;

                  case "invalid_barcode":
                     show_all_other_alerts("Invalid barcode scanned.", "warning");
                     break;

                  default:
                     show_all_other_alerts("Registration failed: " + data.reason, "danger");
               }

               // Reset state so user can scan a new plate
               setTimeout(function() {
                  transition(STATE.BATCH);
               }, 1000); // Give user 1 second to see the error

            } else {
               // Generic server error
               show_all_other_alerts("Server error: " + textStatus + " — " + errorThrown, "danger");
               
               // Reset state
               setTimeout(function() {
                  transition(STATE.BATCH);
               }, 2000);
            }
         },
         dataType: "json"
      });
   }
}

function show_all_other_alerts(message, type="danger") {
   const box = $("#all-other-alerts");
   box.removeClass("alert-danger alert-warning alert-info alert-success");
   box.addClass("alert-" + type);
   box.text(message);
   box.slideDown();
   // Auto-hide after 4 seconds
   setTimeout(() => box.slideUp(), 4000);
}

function reset_plate_errors() {
   $("#duplicate-plate").slideUp();
   $("#duplicate-location").slideUp();
   $("#expired-plate").slideUp();
}


// ============================================
// FLOW ROUTER
// ============================================

function decode_text() {
   var scanned_barcode = text_input; // Capture the current input
   console.log("Request barcode decode: "+scanned_barcode);
   $.ajax({
      type: "POST",
      contentType: "application/json; charset=utf-8",
      url: "/parse",
      data: JSON.stringify(scanned_barcode),
      dataType: "json", //place it with the other config keys for consistency
      success: function (data) {
         console.log(data);

         // Check for configuration errors from /parse endpoint
         if (data.config_error) {
            show_all_other_alerts(
               "CONFIGURATION ERROR: " + data.message, 
               "danger"
            );
            return;
         }

         if (!data || Object.keys(data).length === 0) {
            show_all_other_alerts("Invalid barcode scanned: " + scanned_barcode, "warning");

            text_input = "";  // Clear for next scan

            // Hide positive test warnings since we're clearing state
            $("#no-positive").slideUp();
            reset_plate_errors();

            // Clear the visible field after a delay so user can see what they scanned
            setTimeout(function() {
               $("#barcode").val("");
            }, 4000);  // Clear after 4 seconds

            return;
         }

         // Always reset plate-related alerts on any successful decode
         if ("batch" in data && "serial" in data) {
            reset_plate_errors();
         }
         // Route to appropriate flow
         if ('positive_state' in data) {
            handle_positive_test_required_flow(data);
         } else {
            handle_positive_test_not_required_flow(data);
         }
      },
   });
}

// ============================================
// POSITIVE TEST REQUIRED FLOW
// ============================================

function handle_positive_test_required_flow(data) {
   check_positive(data);
   process_input_positive_required(data);
}

function check_positive(data) {
   if(data.positive_state === "missing") {
      // Clear any previous plate errors when detecting a new missing positive
      reset_plate_errors();

      // Warning for missing positive plate and show registration button
      $("#no-positive-message").text("No positive test for settleplate lot #" + data.lot);
      $("#no-positive").slideDown();
      $("#no-positive-link").show();

      // Store for later registration
      positive_batch = data.no_positive_batch;
      positive_location = data.no_positive_location;
      positive_serial = data.serial;

      // Pre-fill fields immediately
      new_batch = positive_batch;
      new_serial = positive_serial;
      new_location = positive_location;
      update_fields();

      // Disable location field for the positive test plate
      $("#location").prop("disabled", true);

      // Update glyphs to show PASS for all fields
      set_glyph($("#batch_glyph"), GLYPH.PASS);
      set_glyph($("#serial_glyph"), GLYPH.PASS);
      set_glyph($("#location_glyph"), GLYPH.PASS);
      set_glyph($("#input_glyph"), GLYPH.ACTIVE);

      } else if(data.positive_state === "registered_uncounted") {
      // Warning for uncounted positive plate
      $("#no-positive-message").text("Lot #" + data.lot + " has a positive test settleplate with no registered colony counts");
      $("#no-positive").slideDown();
      $("#no-positive-link").hide(); // Hide button but keep warning visible

      new_batch = data.batch;
      update_fields();
      transition(STATE.SERIAL);

      positive_batch = null;
      positive_location = null;
      positive_serial = null;

      // Re-enable location field for subsequent plates
      $("#location").prop("disabled", false);

   } else if(data.positive_state === "completed") {
      // Hide warning entirely
      $("#no-positive").slideUp();

      positive_batch = null;
      positive_location = null;
      positive_serial = null;

      // Clear location field and re-enable it
      new_location = null;
      update_fields();

      // Re-enable location field once Counts have been registered for positive test
      $("#location").prop("disabled", false);
   }
}

function process_input_positive_required(data) {
   // If waiting for positive test registration, don't process state machine
   if(data.positive_state === "missing") {
      return;
   }

   switch(state) {
      case STATE.BATCH:
         if("batch" in data) {
            new_batch = data.batch;
            
            // if backend returned both batch and serial - proceed to location,
            // else Backend returned only batch - wait for serial scan
            if("serial" in data) {
                  new_serial = data.serial;
                  update_table(); // Fetch locations for new batch 
                  transition(STATE.LOCATION);
            }
            else{
            transition(STATE.SERIAL);
            }
         }
         break;
      
      case STATE.SERIAL:
         if("serial" in data && "batch" in data) {
            // check if settleplate already registered
            if(data.used > 0) {
               $("#duplicate-plate").slideDown();
            } else {
               reset_plate_errors();
               new_batch = data.batch;
               new_serial = data.serial;
               transition(STATE.LOCATION);
            }
            let expire = new Date(data.expire);
            if(expire > new Date()) {
               // not expired
               $("#expired-plate").slideUp();
            } else {
               // plate expired
               $("#expired-plate").slideDown();
               $("#expire-date").text(expire.toLocaleDateString());
            }
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
         else if("batch" in data && "serial" in data) {
         // Allow user to scan a different plate if they scanned wrong one when positive test is not required
         if (positive_batch == null) {
            new_batch = data.batch;
            new_serial = data.serial;
            update_fields();
            }
            // If positive test is required, ignore batch+serial scans at LOCATION state
         }
         break;

      default:
         break;
   }
}

function register_positive() {
   $("#no-positive").slideUp();
   new_serial = positive_serial;
   new_location = positive_location;
   new_batch = positive_batch;
   set_glyph($("#location_glyph"),GLYPH.PASS);
   set_glyph($("#batch_glyph"),GLYPH.PASS);
   set_glyph($("#serial_glyph"),GLYPH.PASS);
   update_fields();
   register_new();
}

// ============================================
// POSITIVE TEST NOT REQUIRED FLOW
// ============================================

function handle_positive_test_not_required_flow(data) {
   process_input_positive_not_required(data);
}

function process_input_positive_not_required(data) {
   switch(state) {
      case STATE.BATCH:
         if("batch" in data && "serial" in data) {
            new_batch = data.batch;
            new_serial = data.serial;
            update_fields();
            
            // Load batch locations before transitioning
            update_table(function() {
               transition(STATE.LOCATION);
            });
         }
         break;

      case STATE.SERIAL:
         if("batch" in data && "serial" in data) {
            // Check if settleplate already registered
            if(data.used > 0) {
               $("#duplicate-plate").slideDown();
               // Don't proceed - user must scan a different plate
            } else {
               reset_plate_errors();
               new_batch = data.batch;
               new_serial = data.serial;
               update_fields();

               // Load batch locations before transitioning
               update_table(function() {
               transition(STATE.LOCATION);
            });
         }
      }
      break;

      case STATE.LOCATION:
         if("location" in data) {
            if (location_exist(data["location"])) {
               $("#duplicate-location").slideDown();
            } else {
               $("#duplicate-location").slideUp();
               new_location = data.location;
               update_fields();
               transition(STATE.REGISTER);
            }
         }
         else if("batch" in data && "serial" in data) {// Allow user to correct by scanning a different plate
            reset_plate_errors();
            new_batch = data.batch;
            new_serial = data.serial;
            update_fields();
            
            // Reload batch locations for new batch
            update_table();
         }
         break;

      default:
         break;
   }
}

// ============================================
// INITIALIZATION
// ============================================

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

   // prevent submit on enter press
   $(window).keydown(function(event){
    if(event.keyCode == 13) {
       event.preventDefault();
       return false;
    }
   });
   transition(STATE.BATCH);
})
