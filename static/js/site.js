/*
 * M3M India site behaviour. Each block below replaces one of the old React
 * components; they share a few helpers and run once the DOM is ready.
 */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var lenis = null;

  function $(selector, root) {
    return (root || document).querySelector(selector);
  }

  function $all(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function pad2(number) {
    return String(number).padStart(2, "0");
  }

  /* ---------- Campaign tracking (UTM and ad click IDs) for lead forms ---------- */

  // Each field and the link parameters that fill it: the first one present wins. Old ad templates used
  // {keyword} for the search term and Taboola sends tblci (some links spell it tbcli).
  var TRACKING = {
    utm_source: ["utm_source"],
    utm_medium: ["utm_medium"],
    utm_campaign: ["utm_campaign"],
    utm_term: ["utm_term", "keyword"],
    utm_content: ["utm_content"],
    gclid: ["gclid"],
    matchtype: ["matchtype"],
    fbclid: ["fbclid"],
    tbclid: ["tblci", "tbclid", "tbcli"],
    device: ["device"],
    city: ["city"],
  };

  function initTracking() {
    var params = new URLSearchParams(window.location.search);
    var stored = {};
    try {
      stored = JSON.parse(sessionStorage.getItem("m3m-utm") || "{}");
    } catch (error) {
      stored = {};
    }
    var found = {};
    Object.keys(TRACKING).forEach(function (field) {
      var name = TRACKING[field].filter(function (key) { return params.get(key); })[0];
      if (name) found[field] = params.get(name).slice(0, 255);
    });
    // A visit from a new ad or campaign link replaces what was kept from the previous one.
    if (Object.keys(found).length) {
      stored = found;
      try {
        sessionStorage.setItem("m3m-utm", JSON.stringify(stored));
      } catch (error) {
        /* Storage unavailable: values still go with this page's forms. */
      }
    }
    $all("input[data-utm]").forEach(function (input) {
      input.value = stored[input.name] || "";
    });
    $all("input[data-page-url]").forEach(function (input) {
      input.value = window.location.href.slice(0, 1000);
    });
  }

  /* ---------- Header ---------- */

  function initHeader() {
    var header = $("[data-site-header]");
    if (!header) return;
    var logo = $(".wordmark__logo", header);
    var scrolled = null;

    function update() {
      var next = window.scrollY > 24;
      if (next === scrolled) return;
      scrolled = next;
      header.classList.toggle("site-header--scrolled", scrolled);
      logo.src = scrolled ? logo.dataset.logoTransparent : logo.dataset.logoColor;
      logo.classList.toggle("wordmark__logo--transparent", scrolled);
      logo.classList.toggle("wordmark__logo--color", !scrolled);
    }

    update();
    window.addEventListener("scroll", update, { passive: true });

    var homeLink = $("[data-home-link]");
    homeLink.addEventListener("click", function (event) {
      if (window.location.pathname !== "/") return;
      event.preventDefault();
      if (window.location.hash) {
        history.replaceState(history.state, "", window.location.pathname + window.location.search);
      }
      scrollToTop();
    });
  }

  /* ---------- Smooth scrolling (Lenis + GSAP ScrollTrigger) ---------- */

  function initSmoothScroll() {
    if (reduceMotion || !window.Lenis || !window.gsap) return;
    if (window.ScrollTrigger) gsap.registerPlugin(ScrollTrigger);
    lenis = new Lenis({ autoRaf: false, lerp: 0.08 });
    if (window.ScrollTrigger) lenis.on("scroll", ScrollTrigger.update);
    gsap.ticker.add(function (time) {
      lenis.raf(time * 1000);
    });
    gsap.ticker.lagSmoothing(0);
  }

  function scrollToTop() {
    if (lenis) lenis.scrollTo(0, { immediate: true, force: true });
    else window.scrollTo({ top: 0, behavior: "instant" });
  }

  function initAnchorLinks() {
    document.addEventListener("click", function (event) {
      var link = event.target.closest('a[href^="/#"], a[href^="#"]');
      if (!link || event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey) return;
      var hash = link.getAttribute("href").replace(/^\//, "");
      if (link.getAttribute("href").charAt(0) === "/" && window.location.pathname !== "/") return;
      var target = hash.length > 1 ? document.getElementById(hash.slice(1)) : null;
      if (!target) return;
      event.preventDefault();
      history.pushState(history.state, "", hash);
      // Both Lenis and scrollIntoView respect the CSS scroll-margin-top.
      if (lenis) lenis.scrollTo(target);
      else target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
    });

    // Arriving from another page (e.g. /#media): the browser jumps before the
    // page-enter animation finishes, so re-align once it has.
    var shell = $(".page-shell");
    var initialTarget = window.location.hash.length > 1 && document.getElementById(window.location.hash.slice(1));
    if (shell && initialTarget) {
      shell.addEventListener("animationend", function () {
        if (lenis) lenis.scrollTo(initialTarget, { immediate: true, force: true });
        else initialTarget.scrollIntoView();
      }, { once: true });
    }
  }

  function pauseScroll(paused) {
    if (!lenis) return;
    if (paused) lenis.stop();
    else lenis.start();
  }

  /* ---------- Custom cursor ---------- */

  function initCursor() {
    var cursor = $(".custom-cursor");
    if (!cursor || !window.matchMedia("(pointer: fine)").matches || reduceMotion) return;
    var label = cursor.firstElementChild;

    window.addEventListener(
      "pointermove",
      function (event) {
        cursor.style.setProperty("--cursor-x", event.clientX + "px");
        cursor.style.setProperty("--cursor-y", event.clientY + "px");
        cursor.dataset.visible = "true";
        var labelled = event.target instanceof Element ? event.target.closest("[data-cursor-label]") : null;
        var text = labelled ? labelled.dataset.cursorLabel : "";
        cursor.dataset.label = text;
        cursor.dataset.active = labelled ? "true" : "false";
        label.textContent = text;
      },
      { passive: true },
    );
    document.documentElement.addEventListener("pointerleave", function () {
      cursor.dataset.visible = "false";
    });
  }

  /* ---------- Form helpers ---------- */

  function errorElementFor(control) {
    return control.dataset.errorId ? document.getElementById(control.dataset.errorId) : null;
  }

  function setError(control, message) {
    var errorElement = errorElementFor(control);
    if (control.type !== "radio") {
      control.setAttribute("aria-invalid", message ? "true" : "false");
    }
    if (!errorElement) return;
    errorElement.textContent = message || "";
    errorElement.hidden = !message;
    var hintId = control.dataset.hintId;
    var describedBy = message ? errorElement.id : hintId;
    if (describedBy) control.setAttribute("aria-describedby", describedBy);
    else control.removeAttribute("aria-describedby");
  }

  function setGroupError(id, message) {
    var element = document.getElementById(id);
    if (!element) return;
    element.textContent = message || "";
    element.hidden = !message;
  }

  function setStatus(form, message, success) {
    var status = $("[data-form-status]", form);
    if (!status) return;
    status.classList.toggle("is-success", Boolean(success));
    status.textContent = "";
    if (!message) return;
    if (status.classList.contains("enquiry-form__status")) {
      var paragraph = document.createElement("p");
      paragraph.textContent = message;
      status.appendChild(paragraph);
    } else {
      status.textContent = message;
    }
  }

  function clearForm(form) {
    $all("[data-validate]", form).forEach(function (control) {
      setError(control, "");
    });
    $all(".guided-card__error", form).forEach(function (element) {
      element.textContent = "";
      element.hidden = true;
    });
    setStatus(form, "");
  }

  function validateControls(controls) {
    var firstInvalid = null;
    controls.forEach(function (control) {
      var message = M3MValidation.validateControl(control);
      setError(control, message);
      if (message && !firstInvalid) firstInvalid = control;
    });
    return firstInvalid;
  }

  function submitLead(form, onSuccess) {
    var button = $('button[type="submit"]', form);
    form.setAttribute("aria-busy", "true");
    button.disabled = true;
    setStatus(form, "");

    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    })
      .then(function (response) {
        return response.json().catch(function () {
          return { ok: false };
        });
      })
      .then(function (data) {
        if (data.ok) {
          onSuccess();
          setStatus(form, data.message, true);
          return;
        }
        var first = null;
        Object.keys(data.errors || {}).forEach(function (field) {
          var control = $('[name="' + field + '"]', form);
          if (control && control.dataset.validate) {
            setError(control, data.errors[field]);
            if (!first) first = control;
          }
        });
        if (first) first.focus();
        setStatus(
          form,
          data.message ||
            (first ? "" : "Something went wrong sending your details. Please call or WhatsApp our team."),
        );
      })
      .catch(function () {
        setStatus(form, "We couldn’t reach our server. Please check your connection, or call or WhatsApp our team.");
      })
      .finally(function () {
        form.removeAttribute("aria-busy");
        button.disabled = false;
      });
  }

  function resetLeadFields(form) {
    $all("[data-validate]", form).forEach(function (control) {
      if (control.type === "checkbox") control.checked = false;
      else control.value = "";
    });
  }

  /* ---------- Hero form and enquiry popup ---------- */

  function initLeadForm(form) {
    $all("[data-validate]", form).forEach(function (control) {
      if (control.hasAttribute("data-validate-on-submit")) return;
      var eventName = control.tagName === "SELECT" || control.type === "checkbox" ? "change" : "input";
      control.addEventListener(eventName, function () {
        setError(control, M3MValidation.validateControl(control));
        setStatus(form, "");
      });
      if (control.type !== "checkbox" && !control.hasAttribute("data-no-blur-validate")) {
        control.addEventListener("blur", function () {
          setError(control, M3MValidation.validateControl(control));
        });
      }
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      setStatus(form, "");
      var firstInvalid = validateControls($all("[data-validate]", form));
      if (firstInvalid) {
        firstInvalid.focus();
        return;
      }
      submitLead(form, function () {
        resetLeadFields(form);
      });
    });
  }

  function initEnquiryDialog() {
    var dialog = $("[data-enquiry-dialog]");
    if (!dialog) return;
    var form = $("form", dialog);
    var projectInput = $("[data-enquiry-project]", dialog);
    var projectName = $("[data-enquiry-project-name]", dialog);
    var anyProject = projectName.textContent; // From the admin: “Website texts → Enquiry popup”.
    dialog.setAttribute("data-lenis-prevent", "");

    document.addEventListener("click", function (event) {
      var trigger = event.target.closest("[data-enquiry-open]");
      if (!trigger) return;
      form.reset();
      initTracking();
      clearForm(form);
      projectInput.value = trigger.dataset.project || "";
      projectName.textContent = trigger.dataset.projectName || anyProject;
      if (!dialog.open) dialog.showModal();
      pauseScroll(true);
    });

    $("[data-enquiry-close]", dialog).addEventListener("click", function () {
      dialog.close();
    });
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) dialog.close();
    });
    dialog.addEventListener("close", function () {
      pauseScroll(false);
    });
  }

  /* ---------- Hero banner carousel ---------- */

  function initCarousel() {
    var carousel = $("[data-hero-carousel]");
    if (!carousel) return;
    // Banner videos stay on their poster image for visitors who prefer less motion.
    if (reduceMotion) {
      $all("[data-hero-video]", carousel).forEach(function (video) {
        video.removeAttribute("autoplay");
        video.pause();
      });
    }
    var slides = $all(".hero-banner__slide", carousel);
    if (slides.length < 2) return;
    var dots = $all("[data-carousel-dot]", carousel);
    var toggle = $("[data-carousel-toggle]", carousel);
    var status = $("[data-carousel-status]", carousel);
    var active = 0;
    var paused = reduceMotion;
    var timer = null;

    function show(index) {
      active = index;
      slides.forEach(function (slide, i) {
        slide.classList.toggle("is-active", i === index);
      });
      dots.forEach(function (dot, i) {
        dot.setAttribute("aria-pressed", i === index ? "true" : "false");
      });
      status.textContent = "Banner " + (index + 1) + " of " + slides.length;
    }

    function schedule() {
      clearInterval(timer);
      if (paused) return;
      timer = setInterval(function () {
        show((active + 1) % slides.length);
      }, 6500);
    }

    function renderToggle() {
      toggle.textContent = paused ? "Play" : "Pause";
      toggle.setAttribute("aria-label", paused ? "Play banners" : "Pause banners");
      status.setAttribute("aria-live", paused ? "polite" : "off");
    }

    toggle.addEventListener("click", function () {
      paused = !paused;
      renderToggle();
      schedule();
    });
    dots.forEach(function (dot) {
      dot.addEventListener("click", function () {
        show(Number(dot.dataset.carouselDot));
      });
    });
    renderToggle();
    schedule();
  }

  /* ---------- Animated headings: shared letter splitting ---------- */

  // Puts each letter of an element in its own span, keeping words unbroken.
  // Screen readers read a plain copy of the text instead of the letters.
  function splitLetters(element, className, eachLetter) {
    var text = element.textContent.trim();
    var copy = document.createElement("span");
    copy.className = "visually-hidden";
    copy.textContent = text;
    var letters = document.createElement("span");
    letters.setAttribute("aria-hidden", "true");
    text.split(/(\s+)/).forEach(function (part) {
      if (!part) return;
      if (/^\s+$/.test(part)) {
        letters.appendChild(document.createTextNode(" "));
        return;
      }
      var word = document.createElement("span");
      word.className = "hero-word";
      Array.from(part).forEach(function (letter) {
        var char = document.createElement("span");
        char.className = className;
        char.textContent = letter;
        eachLetter(char);
        word.appendChild(char);
      });
      letters.appendChild(word);
    });
    element.textContent = "";
    element.appendChild(copy);
    element.appendChild(letters);
  }

  /* ---------- Homepage headline: letter animation and mouse tilt ---------- */

  function initHeroHeadline() {
    var headline = $("[data-hero-headline]");
    if (!headline || reduceMotion) return;
    var lines = $all("[data-hero-line]", headline);
    var start = 0.35;
    var step = 0.045;
    var count = 0;
    var waveStart = 0;

    lines.forEach(function (line, lineIndex) {
      if (lineIndex > 0) start += 0.25;
      splitLetters(line, "hero-char", function (char) {
        char.style.setProperty("--d", (start + count * step).toFixed(3) + "s");
        char.style.setProperty("--s", (count * 0.08).toFixed(2) + "s");
        char.dataset.index = count;
        count += 1;
      });
    });

    // The wave starts once every letter has landed, then rolls left to right.
    waveStart = start + count * step + 1.4;
    $all(".hero-char", headline).forEach(function (char) {
      char.style.setProperty("--w", (waveStart + Number(char.dataset.index) * 0.07).toFixed(2) + "s");
    });

    var lastLine = lines[lines.length - 1];
    var flourish = $(".hero-flourish", headline);
    function sizeFlourish() {
      if (flourish && lastLine) headline.style.setProperty("--flourish-width", lastLine.offsetWidth + "px");
    }
    headline.style.setProperty("--flourish-delay", (start + count * step + 0.6).toFixed(2) + "s");
    sizeFlourish();
    window.addEventListener("resize", sizeFlourish);
    if (document.fonts) document.fonts.ready.then(sizeFlourish);

    // The headline leans gently towards the pointer.
    var hero = headline.closest(".phase-one-hero");
    if (!hero || !window.matchMedia("(pointer: fine)").matches) return;
    hero.addEventListener("pointermove", function (event) {
      var box = hero.getBoundingClientRect();
      var x = (event.clientX - box.left) / box.width - 0.5;
      var y = (event.clientY - box.top) / box.height - 0.5;
      headline.style.setProperty("--hero-ry", (x * 10).toFixed(2) + "deg");
      headline.style.setProperty("--hero-rx", (y * -8).toFixed(2) + "deg");
    });
    hero.addEventListener("pointerleave", function () {
      headline.style.setProperty("--hero-ry", "0deg");
      headline.style.setProperty("--hero-rx", "0deg");
    });
  }

  /* ---------- Section headings that slide up into view ---------- */

  function initTitleReveal() {
    var titles = $all("[data-title-reveal]");
    if (!titles.length) return;
    if (reduceMotion || !("IntersectionObserver" in window)) {
      titles.forEach(function (title) {
        title.classList.add("is-in");
      });
      return;
    }
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-in");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -10% 0px" },
    );
    titles.forEach(function (title) {
      observer.observe(title);
    });
  }

  /* ---------- Enquiry form heading: letters quiver like a plucked string ---------- */

  // Used by the banner form heading, the homepage projects heading and the
  // homepage project names. Every heading inside one [data-quiver-box] quivers
  // together, letter after letter. A box quivers when it comes into view, every
  // few seconds while it stays in view (boxes take turns), and on hover.
  function initQuiverTitle() {
    if (reduceMotion) return;
    var boxes = [];
    $all("[data-quiver-title]").forEach(function (title) {
      var box = title.closest("[data-quiver-box]") || title.parentElement;
      if (boxes.indexOf(box) < 0) boxes.push(box);
    });
    boxes.forEach(function (box, order) {
      var titles = $all("[data-quiver-title]", box);
      var index = 0;
      titles.forEach(function (title) {
        splitLetters(title, "quiver-char", function (char) {
          char.style.setProperty("--q", (index * 0.035).toFixed(3) + "s");
          index += 1;
        });
      });

      var busy = false;
      var visible = !("IntersectionObserver" in window);
      function quiver() {
        if (busy || document.hidden) return;
        busy = true;
        box.classList.remove("is-quivering");
        void box.offsetWidth; // Restart the animation.
        box.classList.add("is-quivering");
        setTimeout(function () {
          box.classList.remove("is-quivering");
          busy = false;
        }, 1100 + index * 35);
      }

      if (!visible) {
        new IntersectionObserver(
          function (entries) {
            var nowVisible = entries[0].isIntersecting;
            if (nowVisible && !visible) setTimeout(quiver, 1200 + (order % 4) * 350);
            visible = nowVisible;
          },
          { threshold: 0.4 },
        ).observe(titles[0]);
      }
      setTimeout(function () {
        setInterval(function () {
          if (visible) quiver();
        }, 5000);
      }, (order % 4) * 600);
      box.addEventListener("pointerenter", quiver);
    });
  }


  /* ---------- "Interested in" chips: residential or commercial ---------- */

  function initInterestPick() {
    $all("[data-interest-pick]").forEach(function (group) {
      var input = $('input[name="interest"]', group);
      var chips = $all("[data-interest-value]", group);
      function choose(value) {
        input.value = value;
        chips.forEach(function (chip) {
          chip.setAttribute("aria-pressed", chip.dataset.interestValue === value ? "true" : "false");
        });
      }
      chips.forEach(function (chip) {
        chip.addEventListener("click", function () {
          choose(chip.dataset.interestValue);
          setError(input, "");
        });
      });
      // A hidden field keeps its value through form.reset(), so clear it by hand.
      var form = group.closest("form");
      if (form) {
        form.addEventListener("reset", function () {
          choose("");
        });
      }
    });
  }

  /* ---------- Banner form button: leans towards the pointer, ripples on click ---------- */

  function initFancyButton() {
    if (reduceMotion) return;
    $all("[data-fancy-button]").forEach(function (button) {
      if (window.matchMedia("(pointer: fine)").matches) {
        button.addEventListener("pointermove", function (event) {
          var box = button.getBoundingClientRect();
          var x = (event.clientX - box.left) / box.width - 0.5;
          var y = (event.clientY - box.top) / box.height - 0.5;
          button.style.setProperty("--pull-x", (x * 10).toFixed(1) + "px");
          button.style.setProperty("--pull-y", (y * 6).toFixed(1) + "px");
        });
        button.addEventListener("pointerleave", function () {
          button.style.setProperty("--pull-x", "0px");
          button.style.setProperty("--pull-y", "0px");
        });
      }
      button.addEventListener("pointerdown", function (event) {
        var box = button.getBoundingClientRect();
        var ripple = document.createElement("span");
        ripple.className = "submit-ripple";
        ripple.setAttribute("aria-hidden", "true");
        ripple.style.left = event.clientX - box.left + "px";
        ripple.style.top = event.clientY - box.top + "px";
        button.appendChild(ripple);
        ripple.addEventListener("animationend", function () {
          ripple.remove();
        });
      });
    });
  }

  /* ---------- Homepage gold dust ---------- */

  function initHeroSparkles() {
    var canvas = $("[data-hero-sparkles]");
    if (!canvas || reduceMotion || !canvas.getContext) return;
    var hero = canvas.parentElement;
    var context = canvas.getContext("2d");
    var ratio = Math.min(window.devicePixelRatio || 1, 2);
    var width = 0;
    var height = 0;
    var specks = [];
    var pointer = { x: -9999, y: -9999 };
    var visible = true;
    var frame = null;

    function speck(anywhere) {
      return {
        x: Math.random() * width,
        y: anywhere ? Math.random() * height : height + 10,
        size: 0.6 + Math.random() * 2.2,
        rise: 0.15 + Math.random() * 0.55,
        drift: Math.random() * Math.PI * 2,
        twinkle: Math.random() * Math.PI * 2,
        hue: 38 + Math.random() * 14,
      };
    }

    function resize() {
      width = hero.offsetWidth;
      height = hero.offsetHeight;
      canvas.width = width * ratio;
      canvas.height = height * ratio;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      var total = Math.round(Math.min(110, width / 14));
      specks = [];
      for (var i = 0; i < total; i += 1) specks.push(speck(true));
    }

    function draw() {
      context.clearRect(0, 0, width, height);
      specks.forEach(function (s, i) {
        s.y -= s.rise;
        s.drift += 0.01;
        s.twinkle += 0.05;
        s.x += Math.sin(s.drift) * 0.3;
        // Specks near the pointer are blown softly aside.
        var dx = s.x - pointer.x;
        var dy = s.y - pointer.y;
        var distance = Math.sqrt(dx * dx + dy * dy);
        if (distance > 0 && distance < 120) {
          s.x += (dx / distance) * (120 - distance) * 0.04;
          s.y += (dy / distance) * (120 - distance) * 0.04;
        }
        if (s.y < -10 || s.x < -20 || s.x > width + 20) specks[i] = speck(false);
        var alpha = 0.35 + Math.sin(s.twinkle) * 0.35;
        var glow = context.createRadialGradient(s.x, s.y, 0, s.x, s.y, s.size * 4);
        glow.addColorStop(0, "hsla(" + s.hue + ", 90%, 78%, " + alpha + ")");
        glow.addColorStop(1, "hsla(" + s.hue + ", 90%, 60%, 0)");
        context.fillStyle = glow;
        context.beginPath();
        context.arc(s.x, s.y, s.size * 4, 0, Math.PI * 2);
        context.fill();
      });
      frame = visible && !document.hidden ? requestAnimationFrame(draw) : null;
    }

    function play() {
      if (!frame && visible && !document.hidden) frame = requestAnimationFrame(draw);
    }

    resize();
    window.addEventListener("resize", resize);
    hero.addEventListener("pointermove", function (event) {
      var box = hero.getBoundingClientRect();
      pointer.x = event.clientX - box.left;
      pointer.y = event.clientY - box.top;
    });
    hero.addEventListener("pointerleave", function () {
      pointer.x = pointer.y = -9999;
    });
    document.addEventListener("visibilitychange", play);
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
        play();
      }).observe(hero);
    }
    play();
  }

  /* ---------- Our Journey values ---------- */

  function initJourney() {
    var root = $("[data-journey]");
    if (!root) return;
    var items = $all("[data-journey-item]", root);
    var panel = $("[data-journey-panel]", root);

    items.forEach(function (item) {
      item.addEventListener("click", function () {
        var index = Number(item.dataset.journeyItem);
        items.forEach(function (other) {
          var selected = other === item;
          other.classList.toggle("is-active", selected);
          other.setAttribute("aria-pressed", selected ? "true" : "false");
        });
        panel.setAttribute("aria-labelledby", item.id);
        $("[data-journey-mark]", panel).textContent = "0" + (index + 1);
        $("[data-journey-title]", panel).textContent = item.dataset.title;
        $("[data-journey-description]", panel).textContent = item.dataset.description;
      });
    });
  }

  /* ---------- Press dialog ---------- */

  function initPress() {
    var dialog = $("[data-press-dialog]");
    if (!dialog) return;
    dialog.setAttribute("data-lenis-prevent", "");

    $all("[data-press-open]").forEach(function (card) {
      card.addEventListener("click", function () {
        var data = card.dataset;
        $("[data-press-meta]", dialog).textContent = data.source + " · " + data.date;
        $("[data-press-title]", dialog).textContent = data.title;
        $("[data-press-summary]", dialog).textContent = data.summary;
        $("[data-press-link]", dialog).href = data.url;
        $("[data-press-link-label]", dialog).textContent = "Read the full story on " + data.source;
        var logo = $("[data-press-logo]", dialog);
        logo.hidden = !data.logo;
        if (data.logo) {
          logo.src = data.logo;
          logo.alt = data.source;
        }
        dialog.showModal();
        pauseScroll(true);
      });
    });
    $("[data-press-close]", dialog).addEventListener("click", function () {
      dialog.close();
    });
    dialog.addEventListener("close", function () {
      pauseScroll(false);
    });
  }

  /* ---------- Personalised project discovery ---------- */

  function initGuided() {
    var form = $("[data-guided-form]");
    if (!form) return;

    var interestInputs = $all('input[name="interest"]', form);
    var projectInputs = $all('input[name="project"]', form);
    var residencyInputs = $all('input[name="residency"]', form);
    var contactControls = ["phone", "email", "consent"].map(function (name) {
      return $('[name="' + name + '"]', form);
    });
    // The preview panel is optional: the single-card layout shows the choice on the tile itself.
    var preview = $("[data-guided-preview]", form);
    var previewName = preview && $("[data-guided-preview-name]", preview);
    var previewMeta = preview && $("[data-guided-preview-meta]", preview);
    var emptyName = preview && previewName.textContent;
    var emptyMeta = preview && previewMeta.textContent;

    function checked(inputs) {
      return inputs.filter(function (input) { return input.checked; })[0] || null;
    }

    function markSelected(inputs) {
      inputs.forEach(function (input) {
        input.closest("label").classList.toggle("is-selected", input.checked);
      });
    }

    function interestsOf(input) {
      return input.dataset.interests.split(" ");
    }

    // Show only the projects that match the chosen direction (all of them before a choice).
    function filterProjects() {
      var interest = checked(interestInputs);
      var count = 0;
      projectInputs.forEach(function (input) {
        var show = !interest || interestsOf(input).indexOf(interest.value) !== -1;
        input.closest("label").hidden = !show;
        if (!show) input.checked = false;
        if (show) count += 1;
      });
      $("[data-guided-match-count]", form).textContent = count;
    }

    function renderPreview() {
      if (!preview) return;
      var project = checked(projectInputs);
      var link = $("[data-guided-preview-link]", preview);
      preview.classList.toggle("is-filled", Boolean(project));
      $("[data-guided-preview-empty]", preview).hidden = Boolean(project);
      $("[data-guided-preview-image]", preview).innerHTML = project ? project.dataset.imageHtml : "";
      link.hidden = !project;
      if (!project) {
        previewName.textContent = emptyName;
        previewMeta.textContent = emptyMeta;
        return;
      }
      var residency = checked(residencyInputs);
      previewName.textContent = project.dataset.name;
      previewMeta.textContent = [
        project.dataset.location,
        project.dataset.offering,
        residency ? (residency.value === "nri" ? "For an overseas buyer" : "For a buyer in India") : "",
      ].filter(Boolean).join(" · ");
      link.href = project.dataset.url;
    }

    function renderProgress() {
      var contactDone = contactControls[0].value.trim() && contactControls[1].value.trim();
      var done = [checked(interestInputs), checked(projectInputs), checked(residencyInputs), contactDone]
        .filter(Boolean).length;
      $("[data-guided-progress-count]", form).textContent = done;
      $("[data-guided-progress-bar]", form).style.width = (done / 4) * 100 + "%";
    }

    function update() {
      filterProjects();
      markSelected(interestInputs);
      markSelected(projectInputs);
      markSelected(residencyInputs);
      renderPreview();
      renderProgress();
    }

    interestInputs.forEach(function (input) {
      input.addEventListener("change", function () {
        setGroupError("guided-interest-error", "");
        setStatus(form, "");
        update();
      });
    });

    projectInputs.forEach(function (input) {
      input.addEventListener("change", function () {
        // Picking a project first also picks its direction.
        if (!checked(interestInputs)) {
          var match = interestInputs.filter(function (option) {
            return option.value === interestsOf(input)[0];
          })[0];
          if (match) match.checked = true;
          setGroupError("guided-interest-error", "");
        }
        setGroupError("guided-project-error", "");
        setStatus(form, "");
        update();
      });
    });

    residencyInputs.forEach(function (input) {
      input.addEventListener("change", function () {
        setGroupError("guided-residency-error", "");
        setStatus(form, "");
        update();
      });
    });

    contactControls.forEach(function (control) {
      control.addEventListener(control.type === "checkbox" ? "change" : "input", function () {
        setError(control, "");
        setStatus(form, "");
        renderProgress();
      });
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      setStatus(form, "");
      var firstInvalid = null;
      var groups = [
        [interestInputs, "interest", "Choose what you’re looking for."],
        [projectInputs, "project", "Choose an address for your M3M edit."],
        [residencyInputs, "residency", "Choose where you’re based."],
      ];
      groups.forEach(function (group) {
        var missing = !checked(group[0]);
        setGroupError("guided-" + group[1] + "-error", missing ? group[2] : "");
        if (missing && !firstInvalid) {
          firstInvalid = group[0].filter(function (input) { return !input.closest("label").hidden; })[0];
        }
      });
      var invalidContact = validateControls(contactControls);
      firstInvalid = firstInvalid || invalidContact;
      if (firstInvalid) {
        firstInvalid.focus();
        return;
      }
      submitLead(form, function () {
        resetLeadFields(form);
        renderProgress();
      });
    });

    form.addEventListener("reset", function () {
      setTimeout(update);
    });

    update();
  }

  /* ---------- Menu pages ---------- */

  function setPressed(buttons, active) {
    buttons.forEach(function (button) {
      var on = button === active;
      button.classList.toggle("is-active", on);
      button.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  // Filter pills: `group` holds buttons with data-filter; `apply(value)` does the filtering.
  function initFilterGroup(group, apply) {
    if (!group) return;
    var buttons = $all("[data-filter]", group);
    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        setPressed(buttons, button);
        apply(button.dataset.filter);
      });
    });
    $all("[data-filter-reset]").forEach(function (reset) {
      reset.addEventListener("click", function () {
        setPressed(buttons, buttons[0]);
        apply("all");
      });
    });
  }

  function initProjectFilter() {
    var group = $("[data-project-filter]");
    initFilterGroup(group, function (value) {
      $all("[data-collection]").forEach(function (section) {
        var cards = $all(".project-card", section);
        var shown = 0;
        cards.forEach(function (card) {
          var match = value === "all" || card.dataset.interests.split(" ").indexOf(value) !== -1;
          card.hidden = !match;
          if (match) shown += 1;
        });
        $all('[data-collection-count="' + section.id + '"]').forEach(function (count) {
          count.textContent = shown;
        });
        var empty = $("[data-filter-empty]", section);
        if (empty) empty.hidden = !(cards.length && shown === 0);
      });
    });
  }

  function initScrollspy() {
    var links = $all("[data-scrollspy-link]");
    if (!links.length || !("IntersectionObserver" in window)) return;
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          var key = entry.target.dataset.scrollspySection;
          links.forEach(function (link) {
            link.classList.toggle("is-active", link.dataset.scrollspyLink === key);
          });
        });
      },
      { rootMargin: "-45% 0px -50% 0px" },
    );
    $all("[data-scrollspy-section]").forEach(function (section) {
      observer.observe(section);
    });
  }

  function initGallery() {
    var gallery = $("[data-gallery]");
    if (!gallery) return;
    var items = $all(".masonry__item", gallery);

    initFilterGroup($("[data-gallery-filter]"), function (value) {
      items.forEach(function (item) {
        item.hidden = value !== "all" && item.dataset.category !== value;
      });
    });

    var lightbox = $("[data-lightbox]");
    if (!lightbox) return;
    lightbox.setAttribute("data-lenis-prevent", "");
    var image = $("[data-lightbox-image]", lightbox);
    var current = 0;

    function visibleButtons() {
      return items
        .filter(function (item) { return !item.hidden; })
        .map(function (item) { return $("[data-lightbox-open]", item); });
    }

    function show(index) {
      var buttons = visibleButtons();
      if (!buttons.length) return;
      current = (index + buttons.length) % buttons.length;
      var data = buttons[current].dataset;
      image.src = data.src;
      image.alt = data.caption;
      $("[data-lightbox-caption]", lightbox).textContent = data.caption;
      $("[data-lightbox-category]", lightbox).textContent = data.categoryLabel;
      $("[data-lightbox-count]", lightbox).textContent = current + 1 + " / " + buttons.length;
    }

    gallery.addEventListener("click", function (event) {
      var button = event.target.closest("[data-lightbox-open]");
      if (!button) return;
      show(visibleButtons().indexOf(button));
      lightbox.showModal();
      pauseScroll(true);
    });
    $("[data-lightbox-prev]", lightbox).addEventListener("click", function () { show(current - 1); });
    $("[data-lightbox-next]", lightbox).addEventListener("click", function () { show(current + 1); });
    $("[data-lightbox-close]", lightbox).addEventListener("click", function () { lightbox.close(); });
    lightbox.addEventListener("keydown", function (event) {
      if (event.key === "ArrowLeft") show(current - 1);
      if (event.key === "ArrowRight") show(current + 1);
    });
    lightbox.addEventListener("click", function (event) {
      if (event.target === lightbox) lightbox.close();
    });
    lightbox.addEventListener("close", function () {
      pauseScroll(false);
    });
  }

  function initInsightFilter() {
    var grid = $("[data-insight-grid]");
    if (!grid) return;
    var cards = $all(".insight-card", grid);
    var empty = $("[data-filter-empty]", grid.parentElement);
    initFilterGroup($("[data-insight-filter]"), function (value) {
      var shown = 0;
      cards.forEach(function (card) {
        card.hidden = value !== "all" && card.dataset.category !== value;
        if (!card.hidden) shown += 1;
      });
      if (empty) empty.hidden = shown > 0;
    });
  }

  function initVideos() {
    $all("[data-video-id]").forEach(function (player) {
      player.addEventListener("click", function () {
        var frame = document.createElement("iframe");
        frame.src = "https://www.youtube-nocookie.com/embed/" + player.dataset.videoId + "?autoplay=1&rel=0";
        frame.title = player.getAttribute("aria-label");
        frame.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
        frame.allowFullscreen = true;
        player.replaceChildren(frame);
        player.removeAttribute("aria-label");
      }, { once: true });
    });
  }

  function initCopyLink() {
    $all("[data-copy-link]").forEach(function (button) {
      button.addEventListener("click", function () {
        var done = function () {
          button.textContent = "✓";
          setTimeout(function () { button.textContent = "Link"; }, 2000);
        };
        if (navigator.clipboard) navigator.clipboard.writeText(window.location.href).then(done);
      });
    });
  }

  function initReveal() {
    if (reduceMotion || !("IntersectionObserver" in window)) return;
    var targets = $all(
      ".inner-page .project-card, .value-card, .timeline__item, .masonry__item, .story__collage, " +
        ".inner-page .insight-card, .article-page .insight-card, .feature-article, .contact-form-card, .faq__item, " +
        "[data-bbt-reveal]",
    );
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -8% 0px" },
    );
    targets.forEach(function (target, index) {
      target.setAttribute("data-reveal", "");
      target.style.transitionDelay = (index % 3) * 90 + "ms";
      observer.observe(target);
    });
  }

  // Figures count up the first time they scroll into view. A figure may carry a
  // symbol before it and a unit after it ("₹1,839", "2,279K+", "4.5M"); the
  // number keeps its own commas and decimals. Text like "Jul 2026" is left alone.
  var COUNT_PATTERN = /^([₹$+~]*\s?)(\d[\d,]*(?:\.\d+)?)(\s?[^\d\s][^\d]*)?$/;

  function initCountUp() {
    var figures = $all("[data-count-up]").filter(function (figure) {
      return COUNT_PATTERN.test(figure.textContent.trim());
    });
    if (!figures.length || reduceMotion || !("IntersectionObserver" in window)) return;

    function parse(figure) {
      var match = figure.textContent.trim().match(COUNT_PATTERN);
      var digits = match[2];
      var target = Number(digits.replace(/,/g, ""));
      var plainYear = !match[1] && !match[3] && digits.indexOf(",") < 0 && target >= 1900 && target < 2100;
      return {
        before: match[1],
        after: match[3] || "",
        target: target,
        decimals: (digits.split(".")[1] || "").length,
        // Indian grouping (12,34,567) is kept when the figure is written that way.
        locale: /\d,\d\d,\d{3}/.test(digits) ? "en-IN" : "en-US",
        commas: digits.indexOf(",") >= 0,
        // Years count over their last few years; other figures count from zero.
        start: plainYear ? target - 16 : 0,
      };
    }

    function format(figure, value) {
      var text = figure.commas
        ? value.toLocaleString(figure.locale, { minimumFractionDigits: figure.decimals, maximumFractionDigits: figure.decimals })
        : value.toFixed(figure.decimals);
      return figure.before + text + figure.after;
    }

    function run(element, figure) {
      var began = null;
      element.classList.add("is-counting");
      function frame(time) {
        began = began || time;
        var progress = Math.min((time - began) / 2000, 1);
        var eased = 1 - Math.pow(1 - progress, 4);
        element.textContent = format(figure, figure.start + (figure.target - figure.start) * eased);
        if (progress < 1) {
          requestAnimationFrame(frame);
          return;
        }
        element.textContent = format(figure, figure.target);
        element.classList.remove("is-counting");
        element.classList.add("is-counted");
      }
      requestAnimationFrame(frame);
    }

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        observer.unobserve(entry.target);
        setTimeout(run, entry.target._countDelay, entry.target, entry.target._countUp);
      });
    }, { threshold: 0.6 });
    figures.forEach(function (element, index) {
      element._countUp = parse(element);
      // Hold the finished width so the line does not jump while digits change.
      element.style.minWidth = element.offsetWidth + "px";
      element._countDelay = (index % 3) * 150;
      element.textContent = format(element._countUp, element._countUp.start);
      observer.observe(element);
    });
  }

  function initTeaserVideo() {
    var video = $("[data-bbt-video]");
    if (!video) return;
    if (reduceMotion) {
      video.removeAttribute("autoplay");
      video.pause();
      return;
    }
    if (!("IntersectionObserver" in window)) return;
    new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) video.play().catch(function () {});
        else video.pause();
      });
    }).observe(video);
  }

  /* ---------- Start ---------- */

  function init() {
    initTracking();
    initSmoothScroll();
    initHeader();
    initAnchorLinks();
    initCursor();
    initCarousel();
    initHeroHeadline();
    initHeroSparkles();
    initTitleReveal();
    initQuiverTitle();
    initInterestPick();
    initFancyButton();
    initJourney();
    initPress();
    initEnquiryDialog();
    $all("[data-lead-form]").forEach(function (form) {
      if (!form.hasAttribute("data-guided-form")) initLeadForm(form);
    });
    initGuided();
    initProjectFilter();
    initScrollspy();
    initGallery();
    initInsightFilter();
    initVideos();
    initCopyLink();
    initReveal();
    initCountUp();
    initTeaserVideo();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
