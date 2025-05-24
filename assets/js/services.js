/* This file was developed as part of the Private.coffee project
   It is licensed under the MIT license
   See https://private.coffee for more information */

// Read the available services from a JSON file in the base directory and add them to the displayed services as in index.html
// This function is not currently used by the site, but is included for reference

function loadServices() {
  $("#services").html("");
  $.getJSON("services.json", function (data) {
    $.each(data.services, function (i, service) {
      var serviceHTML =
        '<div class="col-sm-4 service"><h3>' +
        service.name +
        "</h3><p>" +
        service.description +
        '</p><p><a href="' +
        service.url +
        '" target="_blank" class="btn btn-primary">Go to ' +
        service.name +
        "</a></p>";
      if (service.onion) {
        serviceHTML +=
          '<p><a href="' +
          service.onion +
          '" target="_blank" class="btn btn-secondary">' +
          service.onion +
          "</a></p>";
      }
      serviceHTML += "</div>";
      $("#services").append(serviceHTML);
    });
  });
}
