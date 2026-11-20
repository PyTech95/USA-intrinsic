/* Preserve the custom live-editor anti-flash behavior without inline JavaScript. */
(function(){var d=document.documentElement;if(d.hasAttribute("data-prerendered"))return;try{if(localStorage.getItem("intr_live_edits_ready")==="1")return}catch(e){}d.classList.add("le-wait");setTimeout(function(){d.classList.remove("le-wait")},2500)})();
