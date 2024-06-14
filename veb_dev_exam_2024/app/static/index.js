document.addEventListener('DOMContentLoaded', function () {
    // Function to load a new page of books
    function loadPage(page) {
        fetch(`/page/${page}`)
            .then(response => response.text())
            .then(data => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(data, 'text/html');

                // Update books table body
                const newTableBody = doc.querySelector('#books-table-body').innerHTML;
                document.querySelector('#books-table-body').innerHTML = newTableBody;

                // Update pagination
                const newPagination = doc.querySelector('#pagination').innerHTML;
                document.querySelector('#pagination').innerHTML = newPagination;

                // Reattach event listeners to new pagination links
                attachPaginationListeners();
                attachDeleteBookModalListener();
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

    // Function to attach event listener to delete book modal
    function attachDeleteBookModalListener() {
        let deleteBookModal = new bootstrap.Modal(document.getElementById('deleteBookModal'));
        deleteBookModal._element.addEventListener('show.bs.modal', function (event) {
            let button = event.relatedTarget;
            let bookTitle = button.getAttribute('data-book-title');
            let bookId = button.getAttribute('data-book-id');
            let modalBody = deleteBookModal._element.querySelector('.modal-body p');
            let form = deleteBookModal._element.querySelector('form');

            modalBody.textContent = `Вы уверены, что хотите удалить книгу "${bookTitle}"?`;
            form.action = `/delete/${bookId}`;
        });
    }

    // Attach event listeners to initial pagination links
    attachPaginationListeners();
    attachDeleteBookModalListener();
});
