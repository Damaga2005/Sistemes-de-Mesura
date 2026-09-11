(function () {
  "use strict";
  var smUI = window.smUI || null;
  var I18N = window.smI18n || null;
  function tr(k) { return I18N && I18N.t ? I18N.t(k) : k; }
  var root=document.getElementById("review-root"), id=new URLSearchParams(location.search).get("xsid")||"";
  function e(t,c,v){var x=document.createElement(t);if(c)x.className=c;if(v!==undefined)x.textContent=v;return x;}
  function fail(status,msg){
    if(smUI&&smUI.setState){smUI.setState(root,"error",{code:status,message:msg||tr("common.loadError"),retry:status===404||status===403?undefined:load});return;}
    root.innerHTML="";var b=e("div","state-block");b.setAttribute("role",status===403?"alert":"status");b.appendChild(e("h2",null,status===404?"Revisió no trobada":status===403?"Accés prohibit":"Revisió no disponible"));b.appendChild(e("p",null,msg||"La revisió encara no està disponible."));root.appendChild(b);
  }
  function load(){
    if(smUI&&smUI.setState)smUI.setState(root,"loading",{kind:"list"});
    fetch("/api/exam/review?exam_session_id="+encodeURIComponent(id)).then(function(r){return r.json().then(function(d){return {status:r.status,data:d};});}).then(function(res){if(res.status!==200){fail(res.status,res.data.message);return;}var d=res.data;document.getElementById("review-title").textContent=d.title||tr("exam.reviewTitle");document.getElementById("review-sub").textContent=(d.exam_kind||"")+" · "+(d.graded_at||"");root.innerHTML="";root.removeAttribute("aria-busy");(d.questions||[]).forEach(function(q,i){var f=q.feedback||{},card=e("article","card");card.appendChild(e("h2","h3","Pregunta "+((q.position===undefined?i:q.position)+1)));card.appendChild(e("p",null,tr("exam.statusLabel")+": "+(f.status||"—")+" · "+tr("exam.points")+": "+q.points_earned+" / "+q.points_available));if(f.student_answer!==null&&f.student_answer!==undefined)card.appendChild(e("p",null,tr("practice.yourAnswer")+": "+f.student_answer));if(f.formula&&f.formula.latex){var formula=e("div","formula",f.formula.latex);formula.setAttribute("aria-label","Fórmula");card.appendChild(formula);}(f.errors||[]).forEach(function(x){card.appendChild(e("p",null,"Error: "+(x.human||x.type||"—")+(x.severity_band?" · "+x.severity_band:"")));});(f.guidance||[]).forEach(function(x){card.appendChild(e("p","hint",x.hint||""));});root.appendChild(card);if(window.smMath)window.smMath.renderMath(card);});var nav=e("p");var m=e("a","button button--secondary",tr("exam.viewMastery"));m.href="exam.html?xsid="+encodeURIComponent(id)+"#mastery";nav.appendChild(m);var p=e("a","button button--ghost",tr("tutor.practice"));p.href="practice.html";nav.appendChild(p);root.appendChild(nav);}).catch(function(){fail(500,tr("exam.netError"));});
  }
  if(!id){fail(404,tr("exam.missingSessionId"));return;}
  load();
})();
