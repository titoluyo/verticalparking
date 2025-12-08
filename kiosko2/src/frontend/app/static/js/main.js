// Kiosko2 Frontend JavaScript

document.addEventListener('DOMContentLoaded', function() {
    console.log('Kiosko2 Frontend loaded');
    
    // Auto-dismiss flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.flash');
    flashMessages.forEach(function(flash) {
        setTimeout(function() {
            flash.style.opacity = '0';
            setTimeout(function() {
                flash.remove();
            }, 300);
        }, 5000);
    });
});
