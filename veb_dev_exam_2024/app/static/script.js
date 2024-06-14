document.addEventListener('DOMContentLoaded', function () {
    // Function to load a new page of collections
    function loadPage(page) {
        fetch(`/collections/page/${page}`)
            .then(response => response.text())
            .then(data => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(data, 'text/html');

                // Update collections table body
                const newTableBody = doc.querySelector('#collections-table-body').innerHTML;
                document.querySelector('#collections-table-body').innerHTML = newTableBody;

                // Update pagination
                const newPagination = doc.querySelector('#pagination').innerHTML;
                document.querySelector('#pagination').innerHTML = newPagination;

                // Reattach event listeners to new pagination links
                attachPaginationListeners();
                attachDeleteCollectionModalListener();
            })
            .catch(error => console.error('Error loading page:', error));
    }

    // Function to attach event listeners to pagination links
    function attachPaginationListeners() {
        document.querySelectorAll('.page-link').forEach(link => {
            link.addEventListener('click', function (event) {
                event.preventDefault();
                const page = this.getAttribute('data-page');
                if (page) {
                    loadPage(page);
                }
            });
        });
    }

    // Function to attach event listener to delete collection modal
    function attachDeleteCollectionModalListener() {
        let deleteCollectionModal = new bootstrap.Modal(document.getElementById('deleteCollectionModal'));
        deleteCollectionModal.addEventListener('show.bs.modal', function (event) {
            let button = event.relatedTarget;
            let collectionName = button.getAttribute('data-collection-name');
            let collectionId = button.getAttribute('data-collection-id');
            let modalBody = deleteCollectionModal.querySelector('.modal-body p');
            let form = deleteCollectionModal.querySelector('form');

            modalBody.textContent = `Вы уверены, что хотите удалить подборку "${collectionName}"?`;
            form.action = `/collections/delete/${collectionId}`;
        });
    }

    // Attach event listeners to initial pagination links
    attachPaginationListeners();
    attachDeleteCollectionModalListener();
});
