document.addEventListener('DOMContentLoaded', () => {
    // Inject Sidebar
    const sidebarContainer = document.getElementById('sidebar-container');
    if (sidebarContainer) {
        sidebarContainer.innerHTML = `
            <div class="sidebar-header">
                <h2>Swasth<span class="text-primary">AI</span></h2>
            </div>
            <nav class="sidebar-nav">
                <ul>
                    <li><a href="dashboard.html"><i class="fas fa-home"></i> Dashboard</a></li>
                    <li><a href="health-profile.html"><i class="fas fa-user-md"></i> Health Profile</a></li>
                    <li><a href="predictions.html"><i class="fas fa-brain"></i> AI Predictions</a></li>
                    <li><a href="report-analyzer.html"><i class="fas fa-file-medical-alt"></i> Report Analyzer</a></li>
                    <li><a href="ai-assistant.html"><i class="fas fa-robot"></i> AI Assistant</a></li>
                    <li><a href="health-tracking.html"><i class="fas fa-chart-line"></i> Health Tracking</a></li>
                    <li><a href="diet-lifestyle.html"><i class="fas fa-apple-alt"></i> Diet & Lifestyle</a></li>
                    <li><a href="medications.html"><i class="fas fa-pills"></i> Medications</a></li>
                    <li><a href="medical-records.html"><i class="fas fa-folder-open"></i> Medical Records</a></li>
                    <li><a href="family.html"><i class="fas fa-users"></i> Family</a></li>
                    <li><a href="doctors.html"><i class="fas fa-stethoscope"></i> Doctors</a></li>
                    <li><a href="appointments.html"><i class="fas fa-calendar-check"></i> Appointments</a></li>
                </ul>
            </nav>
            <div class="sidebar-footer">
                <a href="login.html"><i class="fas fa-sign-out-alt"></i> Logout</a>
            </div>
        `;
        
        // Highlight active link
        const currentPath = window.location.pathname.split('/').pop();
        const links = sidebarContainer.querySelectorAll('a');
        links.forEach(link => {
            if (link.getAttribute('href') === currentPath) {
                link.classList.add('active');
            }
        });
    }

    // Inject Top Header
    const headerContainer = document.getElementById('header-container');
    if (headerContainer) {
        headerContainer.innerHTML = `
            <div class="header-left">
                <button id="mobile-menu-btn" class="mobile-menu-btn"><i class="fas fa-bars"></i></button>
                <div class="search-bar">
                    <i class="fas fa-search"></i>
                    <input type="text" placeholder="Search records, doctors, etc...">
                </div>
            </div>
            <div class="header-right">
                <button class="icon-btn"><i class="fas fa-bell"></i><span class="badge">3</span></button>
                <div class="user-profile">
                    <img src="https://ui-avatars.com/api/?name=John+Doe&background=0ea5e9&color=fff" alt="User Avatar" class="avatar">
                    <span>John Doe</span>
                </div>
            </div>
        `;
        
        // Mobile menu toggle
        const menuBtn = document.getElementById('mobile-menu-btn');
        if (menuBtn && sidebarContainer) {
            menuBtn.addEventListener('click', () => {
                sidebarContainer.classList.toggle('active');
            });
        }
    }
});
