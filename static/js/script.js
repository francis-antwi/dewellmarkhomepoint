
        // Mobile menu toggle
        const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
        const mainNav = document.querySelector('.main-nav');
        
        mobileMenuToggle.addEventListener('click', () => {
            mainNav.style.display = mainNav.style.display === 'block' ? 'none' : 'block';
        });

        // // Favorite button functionality
        // const favBtns = document.querySelectorAll('.fav-btn');
        // favBtns.forEach(btn => {
        //     btn.addEventListener('click', (e) => {
        //         e.preventDefault();
        //         e.stopPropagation();
        //         const icon = btn.querySelector('i');
        //         if (icon.classList.contains('far')) {
        //             icon.classList.remove('far');
        //             icon.classList.add('fas');
        //             icon.style.color = '#e53e3e';
        //         } else {
        //             icon.classList.remove('fas');
        //             icon.classList.add('far');
        //             icon.style.color = '';
        //         }
        //     });
        // });

        // Property card click handlers
        const propertyCards = document.querySelectorAll('.property-card');
        propertyCards.forEach(card => {
            card.addEventListener('click', (e) => {
                if (!e.target.closest('.fav-btn')) {
                    // Navigate to property details page
                    console.log('Navigate to property details');
                }
            });
        });

        // Smooth scrolling for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth'
                    });
                }
            });
        });

        // Animation on scroll
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }
            });
        }, observerOptions);

        // Observe property cards for animation
        document.querySelectorAll('.property-card').forEach(card => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(30px)';
            card.style.transition = 'all 0.6s ease';
            observer.observe(card);
        });

        // Header scroll effect
        let lastScrollTop = 0;
        const header = document.querySelector('.main-header');
        
        window.addEventListener('scroll', () => {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            
            if (scrollTop > lastScrollTop && scrollTop > 100) {
                header.style.transform = 'translateY(-100%)';
            } else {
                header.style.transform = 'translateY(0)';
            }
            
            lastScrollTop = scrollTop;
        });

        // Auto-close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            const dropdowns = document.querySelectorAll('.dropdown');
            dropdowns.forEach(dropdown => {
                if (!dropdown.contains(e.target)) {
                    dropdown.querySelector('.dropdown-content').style.opacity = '0';
                    dropdown.querySelector('.dropdown-content').style.visibility = 'hidden';
                    dropdown.querySelector('.dropdown-content').style.transform = 'translateY(-10px)';
                }
            });
        });
