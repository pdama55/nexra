(function() {
  function prefersReducedMotion() {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function initNavFadeIn(nav) {
    nav.style.opacity = '0';
    nav.style.transition = 'opacity 0.28s cubic-bezier(0.16, 1, 0.3, 1)';
    setTimeout(function() {
      nav.style.opacity = '1';
    }, prefersReducedMotion() ? 0 : 120);
  }

  function initNavScrollState(nav) {
    function setScrolledState() {
      if (window.scrollY > 10) {
        nav.classList.add('scrolled');
      } else {
        nav.classList.remove('scrolled');
      }
    }

    setScrolledState();
    window.addEventListener('scroll', setScrolledState, { passive: true });
  }

  function initMobileNavDrawer() {
    var toggle = document.getElementById('nav-toggle');
    var drawer = document.getElementById('nav-drawer');
    var overlay = document.getElementById('nav-overlay');
    if (!toggle || !drawer || !overlay) return;

    function setOpen(next) {
      toggle.setAttribute('aria-expanded', next ? 'true' : 'false');
      drawer.setAttribute('aria-hidden', next ? 'false' : 'true');
      drawer.classList.toggle('open', next);
      overlay.hidden = !next;
      document.body.classList.toggle('is-nav-open', next);
    }

    toggle.addEventListener('click', function() {
      var isOpen = toggle.getAttribute('aria-expanded') === 'true';
      setOpen(!isOpen);
    });

    overlay.addEventListener('click', function() {
      setOpen(false);
    });

    drawer.querySelectorAll('[data-nav-close]').forEach(function(link) {
      link.addEventListener('click', function() {
        setOpen(false);
      });
    });

    document.addEventListener('keydown', function(event) {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    });

    window.addEventListener('resize', function() {
      if (window.innerWidth > 900) {
        setOpen(false);
      }
    });
  }

  function easeInOutCubic(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }

  function smoothScroll(target, duration) {
    var el = document.querySelector(target);
    if (!el) return;

    var start = window.scrollY;
    var end = el.getBoundingClientRect().top + start - 72;
    var startTime = null;

    if (prefersReducedMotion()) {
      window.scrollTo(0, end);
      return;
    }

    function step(timestamp) {
      if (!startTime) startTime = timestamp;
      var progress = Math.min((timestamp - startTime) / duration, 1);
      var eased = easeInOutCubic(progress);
      window.scrollTo(0, start + (end - start) * eased);
      if (progress < 1) {
        requestAnimationFrame(step);
      }
    }

    requestAnimationFrame(step);
  }

  function initSmoothScroll() {
    document.querySelectorAll('[data-scroll]').forEach(function(link) {
      var href = link.getAttribute('href');
      if (!href || href.charAt(0) !== '#') return;

      link.addEventListener('click', function(event) {
        event.preventDefault();
        smoothScroll(href, 560);
      });
    });
  }

  function initSharedNavbar() {
    var nav = document.querySelector('.nav');
    if (!nav) return;

    initNavFadeIn(nav);
    initNavScrollState(nav);
    initMobileNavDrawer();
    initSmoothScroll();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSharedNavbar);
  } else {
    initSharedNavbar();
  }
})();
