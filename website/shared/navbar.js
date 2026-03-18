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
    initSmoothScroll();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSharedNavbar);
  } else {
    initSharedNavbar();
  }
})();
