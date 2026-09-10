/* i18n (F17): CA default, ES optional. Chrome strings only; KB content never translated. */
(function () {
  "use strict";
  var DICT = {
    ca: { "nav.inici": "Inici", "nav.temari": "Temari", "nav.practica": "Pràctica",
          "nav.tutor": "Tutor IA", "nav.progres": "Progrés", "nav.examens": "Exàmens",
          "nav.g.estudi": "Estudi", "nav.g.aprendre": "Aprendre", "nav.g.avaluacio": "Avaluació",
          "nav.menu": "Menú", "common.language": "Idioma",
          "common.retry": "Reintenta", "common.loadError": "No hem pogut carregar les dades.",
          "common.empty": "Encara no hi ha activitat.",
          "provider.ready": "Preparat" },
    es: { "nav.inici": "Inicio", "nav.temari": "Temario", "nav.practica": "Práctica",
          "nav.tutor": "Tutor IA", "nav.progres": "Progreso", "nav.examens": "Exámenes",
          "nav.g.estudi": "Estudio", "nav.g.aprendre": "Aprender", "nav.g.avaluacio": "Evaluación",
          "nav.menu": "Menú", "common.language": "Idioma",
          "common.retry": "Reintentar", "common.loadError": "No se han podido cargar los datos.",
          "common.empty": "Aún no hay actividad.",
          "provider.ready": "Preparado" }
  };
  var lang = "ca";
  try { var s = window.localStorage.getItem("sm-lang");
        if (s === "ca" || s === "es") lang = s; } catch (e) { /* no storage: CA */ }
  function t(key) {
    var table = DICT[lang] || DICT.ca;
    return Object.prototype.hasOwnProperty.call(table, key) ? table[key]
         : (DICT.ca[key] !== undefined ? DICT.ca[key] : key);
  }
  function setLang(l) {
    if (l !== "ca" && l !== "es") return;
    lang = l;
    try { window.localStorage.setItem("sm-lang", l); } catch (e) { /* ignore */ }
    document.documentElement.setAttribute("lang", l);
    window.location.reload();
  }
  document.documentElement.setAttribute("lang", lang);
  window.smI18n = { get lang() { return lang; }, t: t, setLang: setLang, dict: DICT };
})();
