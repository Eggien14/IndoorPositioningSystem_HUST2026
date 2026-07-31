/* ============================================================
   Create Map Page JavaScript
   ============================================================ */

// ============================================================
// Form Handling
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    if (!AuthManager.ensureAllowed([1])) {
        return;
    }

    const form = document.getElementById('create-map-form');
    const lengthXInput = document.getElementById('length-x');
    const widthYInput = document.getElementById('width-y');
    const totalCellsSpan = document.getElementById('total-cells');
    const gridAreaSpan = document.getElementById('grid-area');
    
    // Update preview when inputs change
    function updatePreview() {
        const lengthX = parseInt(lengthXInput.value) || 0;
        const widthY = parseInt(widthYInput.value) || 0;
        const totalCells = lengthX * widthY;
        
        totalCellsSpan.textContent = totalCells;
        gridAreaSpan.textContent = `${totalCells} m²`;
    }
    
    lengthXInput.addEventListener('input', updatePreview);
    widthYInput.addEventListener('input', updatePreview);
    
    // Form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const mapName = document.getElementById('map-name').value.trim();
        const lengthX = parseInt(lengthXInput.value);
        const widthY = parseInt(widthYInput.value);
        const offsetAngles = parseFloat(document.getElementById('offset-angles').value || '0');
        
        // Validation
        if (!mapName) {
            alert('Please enter a map name');
            return;
        }
        
        if (lengthX < 1 || lengthX > 100) {
            alert('Width (X) must be between 1 and 100');
            return;
        }
        
        if (widthY < 1 || widthY > 100) {
            alert('Height (Y) must be between 1 and 100');
            return;
        }

        if (Number.isNaN(offsetAngles) || offsetAngles < 0 || offsetAngles >= 360) {
            alert('Offset angle must be in range [0, 360)');
            return;
        }
        
        // Create map
        await createMap({
            map_name: mapName,
            length_x: lengthX,
            width_y: widthY,
            offset_angles: offsetAngles
        });
    });
});

// ============================================================
// Create Map
// ============================================================

async function createMap(mapData) {
    const submitBtn = document.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    
    try {
        // Disable button and show loading state
        submitBtn.disabled = true;
        submitBtn.textContent = i18n.translate('msg.saving');
        
        const response = await API.post('/api/maps', mapData);
        
        if (response.success) {
            showToast(i18n.translate('createMap.success'), 'success');
            
            // Redirect to choose map page after short delay
            setTimeout(() => {
                window.location.href = '/choose-map';
            }, 500);
        }
    } catch (error) {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
        
        // Check if it's a duplicate ID error (though ID is auto-increment)
        showToast(i18n.translate('createMap.error') + ': ' + error.message, 'error');
    }
}
