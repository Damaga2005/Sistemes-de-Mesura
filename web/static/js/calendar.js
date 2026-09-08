(function () {
  "use strict";
  var root = document.getElementById("calendar-root");
  fetch("/api/calendar")
    .then(function (response) { return response.json(); })
    .then(function (data) {
      root.innerHTML = "";
      var title = document.createElement("h2");
      title.className = "h3";
      title.textContent = data.configured ? "Esdeveniments" : "Calendari buit";
      root.appendChild(title);
      var message = document.createElement("p");
      message.textContent = data.message || "No hi ha esdeveniments.";
      root.appendChild(message);
      var source = document.createElement("p");
      source.className = "hint";
      source.textContent = "Font: " + data.source;
      root.appendChild(source);
    })
    .catch(function () {
      root.textContent = "No s'ha pogut carregar el calendari.";
    });
}());
