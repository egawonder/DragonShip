import pygame

if __name__ == '__main__':
    pygame.init()
    pygame.display.set_mode((640, 480), 0, 32)
    pygame.display.set_caption("Key Check")

    print("Press and key to view key code")

    pygame.WINDOWCLOSE
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                print(repr(event))