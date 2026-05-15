var new_batch;
var new_serial;
var new_location;
var new_full_barcode; //track full GS1 barcode
//initialise to safe defaults
var text_input = "";
var batch_locations = [];
var positive_batch;
var positive_location;
var positive_serial;
var positive_full_barcode; //track full GS1 barcode for first positive plate
var state;
var saved_batch;
var new_lot;
var new_expire;
//tracks whether batch_locations is ready to query
var tableReady = Promise.resolve();

const GLYPH = {
   WAIT: 'wait',
   PASS: 'pass',
   FAIL: 'fail',
   ACTIVE: 'active'
}

const STATE = {
   RESET:    'reset',
   SERIAL:   'serial',
   LOCATION: 'location',
   REGISTER: 'register',
   LOOP:     'loop'
}

// transition state machine
function transition(new_state) {
    console.log(`New state: ${new_state}`);
    switch(new_state) {
        case STATE.LOOP:
            new_serial   = null;
            new_location = null;
            new_lot = null;
            new_expire = null;
            new_full_barcode = null,
            set_glyph($("#location_glyph"), GLYPH.WAIT);
            // fall through to SERIAL

        case STATE.SERIAL:
            update_fields();
            if (new_batch != null) {
                update_table();
            }
            set_glyph($("#serial_glyph"),   GLYPH.ACTIVE);
            state = STATE.SERIAL;
            break;

        case STATE.LOCATION:
            update_fields();
            set_glyph($("#serial_glyph"),   GLYPH.PASS);
            set_glyph($("#location_glyph"), GLYPH.ACTIVE);
            state = STATE.LOCATION;
            break;

        case STATE.REGISTER:
            set_glyph($("#location_glyph"), GLYPH.PASS);
            state = STATE.REGISTER;
            register_new();
            break;
    }
}

function process_input(data) {
    //Always derive batch from serial scan
    if (data.lot) {
        if (new_batch !== data.lot) {
            new_batch   = data.lot;
            saved_batch = data.lot;
           
            $("#table_registered").empty();   // clear old table
            update_table();   // refresh table immediately on lot change
        }

        update_fields();   // ensure batch field updates immediately on scan

        // Redirect to SERIAL only if not already there
        if (state !== STATE.SERIAL) {
            transition(STATE.SERIAL);
            return;
        }
        // Already in SERIAL, fall through
    }

    switch(state) {
        case STATE.SERIAL:
            if("plate_barcode" in data) {
                // always clear duplicate warning on any new serial scan
                hide($("#duplicate-plate"));

                // guard against missing expire date
                if (data.expire) {
                    let expire = new Date(data.expire);
                    if (!isNaN(expire.getTime())) {
                        if(expire > new Date()) {
                            hide($("#expired-plate"));
                        } else {
                            show($("#expired-plate"));
                            $("#expire-date").text(expire.toLocaleDateString());
                        }
                    } else {
                        hide($("#expired-plate"));
                    }
                } else {
                    hide($("#expired-plate"));   // ensures UI resets
                }

                // -----> FIXED: warn if positive exists but not counted
                if (POSITIVE_TEST_REQUIRED && data.positive_pending) {
                     $("#positive-pending-lot").text(data.lot);
                     show($("#positive-pending"));
                } else {
                    hide($("#positive-pending"));
                }

                // check if settleplate already registered, if so exit early
                if(data.used && data.used > 0) {
                    show($("#duplicate-plate"));
                    return;
                } 

                // store GS1 plate serial + full GS1 barcode
                new_serial = data.plate_serial;
                new_full_barcode = data.plate_barcode;

                // store GS1 data
               if("lot" in data)
                     new_lot = data.lot;
               if("expire" in data)
                     new_expire = data.expire;

                // If positive test required and none exists yet,
                // do NOT advance to location — wait for positive registration.
                // check_positive() will have already shown the warning + button.
                if (POSITIVE_TEST_REQUIRED && data.no_positive) {
                    // Stay in SERIAL state; user must click "Register now" first.
                    positive_serial   = data.plate_serial;
                    positive_full_barcode = data.plate_barcode;
                    positive_batch    = data.no_positive_batch;
                    positive_location = data.no_positive_location;
                    new_location = null;

                    $("#no-positive-lot").text(data.lot);
                    show($("#no-positive"));
                    //Update fields so the serial is visible.
                    update_fields();
                    return;
                }
                hide($("#no-positive"));
                transition(STATE.LOCATION);
            }
            break;

        case STATE.LOCATION:
            if("location" in data) {
               var handleLocation = function() {
                    if (location_exist(data["location"])) {
                        show($("#duplicate-location"));
                    } else {
                        hide($("#duplicate-location"));
                        new_location = data.location;
                        transition(STATE.REGISTER);
                    }
                }
                 // wait for async table readiness
                if (tableReady && typeof tableReady.then === "function") {
                    tableReady.then(handleLocation);
                } else {
                    handleLocation();
                }
            }
            break;

        default:
            break;
   }
}

function set_glyph(glyph, state) {
   glyph.toggleClass('fa-question-circle',    state == GLYPH.WAIT);
   glyph.toggleClass('fa-check-circle',       state == GLYPH.PASS);
   glyph.toggleClass('fa-exclamation-circle', state == GLYPH.FAIL);
}

function update_table() {
    // reset state when no batch
    if(new_batch == null) {
        batch_locations = [];
        tableReady = Promise.resolve();
        return;
    }
    //async tracking
    tableReady = new Promise(function(resolve) {

        $.ajax({
            type: "POST",
            contentType: "application/json; charset=utf-8",
            url: "/settleplate/batch_bydate",
            data: JSON.stringify({'batch': new_batch}),
                success: function (data) {
                    batch_locations = data;
                    console.log(batch_locations);
                    $("#table_registered").empty();
                    for(var i=0; i<batch_locations.length; i++) {
                        $("#table_registered").append(`
                            <tr>
                                <td>${batch_locations[i].ScanDate}</td>
                                <td>${batch_locations[i].Barcode}</td>
                                <td>${batch_locations[i].Location}</td>
                            </tr>
                        `)
                    }
                    resolve();
                },
                error: function () {
                    console.warn("update_table failed");
                    batch_locations = [];
                    resolve();
                },
            dataType: "json"
        });
    });
}

function location_exist(location) {
   for(var i=0; i<batch_locations.length; i++) {
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

function register_positive() {
    hide($("#no-positive"));
    new_serial   = positive_serial;
    new_full_barcode = positive_full_barcode;
    new_location = positive_location;
    new_batch = positive_batch; // prefix+lot
    set_glyph($("#location_glyph"), GLYPH.PASS);
    set_glyph($("#batch_glyph"),    GLYPH.PASS);
    set_glyph($("#serial_glyph"),   GLYPH.PASS);
    update_fields();
    // go to register directly
    transition(STATE.REGISTER);
}

function register_new() {
   if(new_batch != null && new_serial != null && new_location != null) {
      $.ajax({
         type: "POST",
         contentType: "application/json; charset=utf-8",
         url: "/settleplate/register",
         data: JSON.stringify({batch:new_batch, plate_serial:new_serial, location:new_location, lot:new_lot, expire:new_expire, full_barcode: new_full_barcode}),
            success: function (data) {
               console.log(data);
               setTimeout(function() {
                hide_warnings_synchronized();

                setTimeout(function() {
                    transition(STATE.LOOP);
                    }, 300); //wait for animation to finish
               }, 1000);
            },
            error: function (XMLHttpRequest, textStatus, errorThrown) {
                console.error("SERVER ERROR:", XMLHttpRequest.responseText);
                try {
                    const response = JSON.parse(XMLHttpRequest.responseText);
                    show_error(response?.error?.message || "Registration failed");
                } catch (e) {
                    show_error("Registration failed: " + (errorThrown || textStatus));
                }
            },
         dataType: "json"
      });
   }
}

function decode_text() {
   console.log("Request barcode decode: " + text_input);
   $.ajax({
      type: "POST",
      contentType: "application/json; charset=utf-8",
      url: "/parse",
      data: JSON.stringify(text_input),
        // On success (HTTP 200), backend doesnot return any warnings
         success: function (data) {
            console.log(data);
            process_input(data);
         },

         error: function (XMLHttpRequest) {
             console.error("SERVER ERROR:", XMLHttpRequest.responseText);
             try{
                const response = JSON.parse(XMLHttpRequest.responseText);
                show_error(response?.error?.message || "Unknown error");
                } catch (e) {
                    show_error("Invalid response from server");
                }
         },
      dataType: "json"
   });
}

function show_error(message) {
    $("#invalid-barcode")
        .text(message)
        .stop(true, true)
        .fadeIn(200)
        .delay(2000)
        .fadeOut(400);
}

function hide_warnings_synchronized() {
    hide($("#duplicate-plate"));
    hide($("#duplicate-location"));
    hide($("#expired-plate"));
    hide($("#no-positive"));
    hide($("#positive-pending"));

}


function show(el) {
    el.stop(true, true).slideDown();
}

function hide(el) {
    el.stop(true, true).slideUp();
}


//Init
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
   // Starting state
   transition(STATE.SERIAL);
});