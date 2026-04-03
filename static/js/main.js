// Initialize AOS
AOS.init({
    duration: 700,
    once: true,
    offset: 60
});

// Mobile menu
const hamburger = document.querySelector('.hamburger');
const navLinks = document.querySelector('.nav-links');

if (hamburger) {
    hamburger.addEventListener('click', () => {
        navLinks.classList.toggle('active');
    });
}

// Close menu when clicking outside
document.addEventListener('click', (e) => {
    if (navLinks && navLinks.classList.contains('active')) {
        if (!navLinks.contains(e.target) && !hamburger.contains(e.target)) {
            navLinks.classList.remove('active');
        }
    }
});

// Auto-hide flash messages
setTimeout(() => {
    document.querySelectorAll('.flash').forEach(flash => {
        flash.style.opacity = '0';
        setTimeout(() => flash.remove(), 500);
    });
}, 5000);

console.log('🚀 Evolution Media — Loaded');
