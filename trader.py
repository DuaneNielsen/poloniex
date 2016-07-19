import api  

class account():
    apikey = 'FJWBROLE-0EXP269H-5O4JSG2H-Q6DYCSVI'
    secret = 'bacb3341bbce361978e34807e5487d88331b06487fcbddbf0b027192e17b2e40145b0ecbdfce020a3c064233b84601a8a0cc6322c54ed9ea39a6fb989e439ec3'
    polo = api.poloniex(apikey,secret)

    def tikker(self):
        t = self.polo.api_query("returnTicker")
        print(t)
        
    def realaccnt(self):
        return polo

def main():
    print("main started")

if __name__ == "__main__":
    main()