(function () {
  "use strict";
  var smUI = window.smUI || null;
  var I18N = window.smI18n || null;
  function tr(k) { return I18N && I18N.t ? I18N.t(k) : k; }
  var root=document.getElementById("results-root"), id=new URLSearchParams(location.search).get("xsid")||"";
  function e(t,c,v){var x=document.createElement(t);if(c)x.className=c;if(v!==undefined)x.textContent=v;return x;}
  function fail(status,msg){
    if(smUI&&smUI.setState){smUI.setState(root,"error",{code:status,message:msg||tr("common.loadError"),retry:status===404||status===403?undefined:load});return;}
    root.innerHTML="";var b=e("div","state-block");b.setAttribute("role",status===403?"alert":"status");b.appendChild(e("h2",null,status===404?"Resultat no trobat":status===403?"Accés prohibit":"Resultat no disponible"));b.appendChild(e("p",null,msg||"El resultat no està disponible en aquest estat."));root.appendChild(b);
  }
  function load(){
    if(smUI&&smUI.setState)smUI.setState(root,"loading",{kind:"card"});
    fetch("/api/exam/result?exam_session_id="+encodeURIComponent(id)).then(function(r){return r.json().then(function(d){return {status:r.status,data:d};});}).then(function(res){if(res.status!==200){fail(res.status,res.data.message);return;}var r=res.data;document.getElementById("results-title").textContent=r.title||"Resultats";document.getElementById("results-sub").textContent=(r.exam_kind||"")+" · "+(r.graded_at||"");root.innerHTML="";root.removeAttribute("aria-busy");var card=e("section","card");card.appendChild(e("h2","h3","Resum"));card.appendChild(e("p",null,"Percentatge: "+r.percentage));card.appendChild(e("p",null,"Punts: "+r.earned_points+" / "+r.total_points));card.appendChild(e("p",null,"Respostes: "+r.answered_count+" · En blanc: "+r.blank_count));card.appendChild(e("p",null,"Correctes: "+r.correct_count+" · Parcials: "+r.partial_count+" · Incorrectes: "+r.incorrect_count));card.appendChild(e("p","hint","Provenance: "+(r.provenance&&r.provenance.scoring_policy_version||"no disponible")));root.appendChild(card);var nav=e("p");var review=e("a","button","Veure revisió");review.href="review.html?xsid="+encodeURIComponent(id);nav.appendChild(review);root.appendChild(nav);}).catch(function(){fail(500,"Error de xarxa.");});
  }
  if(!id){fail(404,"Falta l'identificador de sessió.");return;}
  load();
})();
